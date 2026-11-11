# ============================================================================
# File: macro_dashboard/macro/catalog.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\macro\catalog.py
"""Sarjaluettelon lataus (``catalog/*.yaml``) ja laajennus yksittäisiksi hakuehdokkaiksi.

Yksi indikaattori x alue = yksi ``SeriesDef``. Jokaisella on järjestetty lista
hakuehdokkaita (``Cand``): ensimmäinen, joka palauttaa tuoreen datan, voittaa.
Näin esim. euroalueen geo-koodi (EA21/EA20/EA) tai poistunut OECD-sarja
korvautuu varavaihtoehdolla ilman koodimuutoksia.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

try:  # PyYAML, jos asennettu; muuten puhdas-Python ruamel.yaml (ei vaadi käännöstä, esim. Python 3.15)
    import yaml as _yaml

    def _load_yaml(text: str) -> Any:
        return _yaml.safe_load(text)
except ImportError:  # pragma: no cover
    from ruamel.yaml import YAML as _YAML

    def _load_yaml(text: str) -> Any:
        return _YAML(typ="safe").load(text)

from data_fetchers import Frequency, SeriesSpec

__all__ = ["Cand", "SeriesDef", "Indicator", "Region", "Catalog", "load_catalog"]

_FREQ = {"D": Frequency.DAILY, "M": Frequency.MONTHLY, "Q": Frequency.QUARTERLY, "A": Frequency.ANNUAL}


@dataclass(frozen=True)
class Cand:
    source: str
    code: str
    freq: Frequency
    params: Mapping[str, Any] = field(default_factory=dict)
    post: str | None = None
    geo: str | None = None

    @property
    def raw_key(self) -> str:
        """Lähdedatan avain: sama haku jaetaan eri muunnosten (yoy/m-m) kesken."""
        blob = json.dumps([self.source, self.code, self.freq.value, self.params, self.geo], sort_keys=True)
        h = hashlib.sha1(blob.encode()).hexdigest()[:8]
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.code)[:40]
        return f"{self.source}_{safe}_{h}"

    def to_spec(self) -> SeriesSpec:
        if self.source == "eurostat":
            extra: dict[str, Any] = {"filters": dict(self.params)}
        elif self.source == "fred":
            extra = {"params": dict(self.params)}
        else:
            extra = dict(self.params)
        return SeriesSpec(
            series_id=self.raw_key, source_code=self.code, frequency=self.freq,
            geo=self.geo, extra=extra,
        )


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    geo: tuple[str, ...] = ()  # Eurostat-geo-ehdokkaat järjestyksessä
    oecd: tuple[str, ...] = ()  # OECD:n REF_AREA-ehdokkaat järjestyksessä
    ref: bool = False  # piirretäänkö viitelinjana muiden alueiden sivuilla
    color: str | None = None


@dataclass(frozen=True)
class Indicator:
    id: str
    title: str
    theme: str
    unit: str
    freq: Frequency
    kind: str = "line"  # alueen sivulla: "line" | "bar"
    decimals: int = 1
    years: int = 10  # kuvion pituus
    note: str | None = None


@dataclass
class SeriesDef:
    id: str  # "FI.cpi_yoy"
    indicator: str
    region: str
    cands: list[Cand]


@dataclass
class Catalog:
    regions: dict[str, Region]
    indicators: dict[str, Indicator]
    series: list[SeriesDef]
    themes: dict[str, str]  # teema-id -> otsikko (järjestys säilyy)

    def series_of(self, indicator: str) -> list[SeriesDef]:
        return [s for s in self.series if s.indicator == indicator]


def _as_list(x: Any) -> list:
    return x if isinstance(x, list) else [x]


def _freq(code: str) -> Frequency:
    try:
        return _FREQ[code]
    except KeyError:
        raise ValueError(f"Tuntematon taajuus {code!r}; sallitut: {sorted(_FREQ)}") from None


def load_catalog(path: str | Path) -> Catalog:
    """Lataa yksi YAML-tiedosto tai kaikki ``*.yaml`` kansiosta (yhdistetään)."""
    path = Path(path)
    files = sorted(path.glob("*.yaml")) if path.is_dir() else [path]
    if not files:
        raise FileNotFoundError(f"Ei luettelotiedostoja: {path}")

    regions: dict[str, Region] = {}
    themes: dict[str, str] = {}
    raw_inds: list[dict] = []
    for f in files:
        data = _load_yaml(f.read_text(encoding="utf-8")) or {}
        for rid, r in (data.get("regions") or {}).items():
            regions[rid] = Region(
                id=rid, name=r["name"], geo=tuple(_as_list(r.get("geo", []))),
                oecd=tuple(_as_list(r.get("oecd", []))), ref=bool(r.get("ref", False)),
                color=r.get("color"),
            )
        themes.update(data.get("themes") or {})
        raw_inds.extend(data.get("indicators") or [])

    indicators: dict[str, Indicator] = {}
    series: list[SeriesDef] = []
    for d in raw_inds:
        if d["id"] in indicators:
            raise ValueError(f"Indikaattori {d['id']!r} on määritelty kahdesti")
        if d["theme"] not in themes:
            raise ValueError(f"{d['id']}: tuntematon teema {d['theme']!r}")
        ind = Indicator(
            id=d["id"], title=d["title"], theme=d["theme"], unit=d.get("unit", ""),
            freq=_freq(d.get("freq", "M")), kind=d.get("kind", "line"),
            decimals=int(d.get("decimals", 1)), years=int(d.get("years", 10)), note=d.get("note"),
        )
        indicators[ind.id] = ind

        by_region: dict[str, list[Cand]] = {}

        for block in _as_list(d.get("eurostat") or []):
            for rid in block.get("regions", []):
                if rid not in regions:
                    raise ValueError(f"{ind.id}: tuntematon alue {rid!r}")
                for geo in regions[rid].geo:
                    by_region.setdefault(rid, []).append(Cand(
                        "eurostat", block["code"], _freq(block.get("freq", d.get("freq", "M"))),
                        {**block.get("filters", {}), "geo": geo}, block.get("post"), geo,
                    ))

        for block in _as_list(d.get("oecd") or []):
            for rid in block.get("regions", []):
                if rid not in regions:
                    raise ValueError(f"{ind.id}: tuntematon alue {rid!r}")
                for area in regions[rid].oecd:
                    by_region.setdefault(rid, []).append(Cand(
                        "oecd", block["flow"], _freq(block.get("freq", d.get("freq", "M"))),
                        {"key": block["key"].format(geo=area)}, block.get("post"), area,
                    ))

        for rid, entries in (d.get("other") or {}).items():
            if rid not in regions:
                raise ValueError(f"{ind.id}: tuntematon alue {rid!r}")
            for e in _as_list(entries):
                by_region.setdefault(rid, []).append(Cand(
                    e["source"], e["code"], _freq(e.get("freq", d.get("freq", "M"))),
                    dict(e.get("params", {})), e.get("post"), e.get("geo"),
                ))

        for rid in regions:  # alueiden järjestys = regions-lohkon järjestys
            if rid in by_region:
                series.append(SeriesDef(id=f"{rid}.{ind.id}", indicator=ind.id, region=rid, cands=by_region[rid]))

    return Catalog(regions=regions, indicators=indicators, series=series, themes=themes)
