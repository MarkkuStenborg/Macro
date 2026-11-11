# ============================================================================
# File: macro_dashboard/macro/update.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\macro\update.py
"""Hae luettelon sarjat varastoon.

* Jokaiselle sarjalle kokeillaan hakuehdokkaat järjestyksessä; ensimmäinen, jonka
  tuorein havainto ei ole liian vanha (``max_stale_months``), voittaa. Jos kaikki
  ovat vanhoja, käytetään tuorein vanha (ja merkitään ``stale``).
* Sama lähdehaku (raw_key) tehdään vain kerran, vaikka se palvelee usea muunnos (y/y, m/m).
* Rinnakkaisuus: eri lähteet ajetaan samanaikaisesti; ``concurrency`` rajaa samaan
  lähteeseen kohdistuvien hakujen määrän (FRED/OECD peräkkäin).
* Yhden sarjan virhe ei kaada muita.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import pandas as pd

from data_fetchers import Frequency, fetch_series
from .catalog import Cand, Catalog, SeriesDef
from .store import Store

__all__ = ["update_catalog", "UpdateReport"]

DEFAULT_CONCURRENCY = {"eurostat": 4, "fred": 1, "oecd": 1, "imf": 1, "bundesbank": 1, "worldbank": 2, "dbnomics": 2}


@dataclass
class UpdateReport:
    ok: dict[str, dict[str, Any]]
    failed: dict[str, str]
    fetched: int  # verkkohakujen määrä
    cached: int

    def lines(self) -> list[str]:
        out = []
        for sid, info in sorted(self.ok.items()):
            tag = " (VANHA)" if info.get("stale") else ""
            out.append(f"OK    {sid:<28} {info['source']}:{info['code']} {info.get('geo') or ''} viim. {info['last_obs']}{tag}")
            for why in info.get("skipped") or []:
                out.append(f"        ↳ ensin hylätty: {why}")
        for sid, err in sorted(self.failed.items()):
            out.append(f"EI    {sid:<28} {err}")
        return out


def update_catalog(
    catalog: Catalog,
    store: Store,
    *,
    today: pd.Timestamp | None = None,
    history_years: int = 25,
    max_age_hours: float = 12.0,
    max_stale_months: int = 18,
    force: bool = False,
    only_themes: set[str] | None = None,
    fetch: Callable[..., pd.DataFrame] = fetch_series,
    fetch_kwargs: Mapping[str, Mapping[str, Any]] | None = None,
    concurrency: Mapping[str, int] | None = None,
    log: Callable[[str], None] = lambda m: None,
) -> UpdateReport:
    today = today if today is not None else pd.Timestamp.today().normalize()
    start = today - pd.DateOffset(years=history_years)
    limits = {**DEFAULT_CONCURRENCY, **(concurrency or {})}
    sems: dict[str, threading.Semaphore] = {}
    key_locks: dict[str, threading.Lock] = {}
    guard = threading.Lock()
    counters = {"fetched": 0, "cached": 0}
    mem_err: dict[str, str] = {}

    def sem(source: str) -> threading.Semaphore:
        with guard:
            return sems.setdefault(source, threading.Semaphore(limits.get(source, 2)))

    def klock(key: str) -> threading.Lock:
        with guard:
            return key_locks.setdefault(key, threading.Lock())

    def get_raw(c: Cand) -> pd.Series:
        key = c.raw_key
        with klock(key):
            if key in mem_err:
                raise RuntimeError(mem_err[key])
            if not force and store.is_fresh(key, max_age_hours):
                counters["cached"] += 1
                s = store.load(key)
                assert s is not None
                return s
            meta = {"source": c.source, "code": c.code, "geo": c.geo, "params": dict(c.params), "freq": c.freq.value}
            try:
                with sem(c.source):
                    df = fetch(c.source, [c.to_spec()], start=start, **dict((fetch_kwargs or {}).get(c.source, {})))
                s = df.iloc[:, 0].dropna()
                if s.empty:
                    raise RuntimeError("ei havaintoja")
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                mem_err[key] = msg
                store.save_error(key, meta, msg)
                raise RuntimeError(msg) from exc
            counters["fetched"] += 1
            store.save(key, s, meta)
            return s

    def resolve(sd: SeriesDef) -> tuple[str, dict[str, Any] | None, str | None]:
        errors: list[str] = []
        best: tuple[Cand, pd.Timestamp] | None = None
        for c in sd.cands:
            try:
                s = get_raw(c)
            except Exception as exc:
                errors.append(f"{c.geo or c.code}: {exc}"[:160])
                continue
            last = s.index[-1]
            # vuosisarjalla viive on rakenteellisesti 1-2 vuotta (esim. Maailmanpankki): +18 kk
            extra = 18 if c.freq is Frequency.ANNUAL else 0
            cutoff = today - pd.DateOffset(months=max_stale_months + extra)
            if last >= cutoff:
                return sd.id, _info(c, last, stale=False, skipped=errors), None
            if best is None or last > best[1]:
                best = (c, last)
            errors.append(f"{c.geo or c.code}: vanha ({last:%Y-%m})")
        if best is not None:
            return sd.id, _info(best[0], best[1], stale=True, skipped=errors), None
        return sd.id, None, " | ".join(errors)[:300]

    def _info(c: Cand, last: pd.Timestamp, stale: bool, skipped: list[str] | None = None) -> dict[str, Any]:
        return {"raw_key": c.raw_key, "source": c.source, "code": c.code, "geo": c.geo, "post": c.post,
                "freq": c.freq.value, "last_obs": last.strftime("%Y-%m-%d"), "stale": stale,
                "skipped": list(skipped or [])}

    todo = [sd for sd in catalog.series
            if only_themes is None or catalog.indicators[sd.indicator].theme in only_themes]
    # ryhmittele ensimmäisen ehdokkaan lähteen mukaan: samaan lähteeseen ei kohdistu liikaa rinnakkaisuutta
    resolved: dict[str, dict[str, Any]] = {}
    failed: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for sid, info, err in pool.map(resolve, todo):
            if info is not None:
                resolved[sid] = info
            else:
                failed[sid] = err or "tuntematon virhe"
            log(f"{sid}: {'ok' if info else 'EI'}")
    store.flush()
    # säilytä muiden teemojen aiemmat ratkaisut, jos ajettiin vain osa
    merged = {**store.load_resolved(), **resolved} if only_themes else resolved
    for sid in failed:
        merged.pop(sid, None)
    store.save_resolved(merged)
    return UpdateReport(ok=resolved, failed=failed, fetched=counters["fetched"], cached=counters["cached"])
