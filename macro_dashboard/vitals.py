# ============================================================================
# File: macro_dashboard/vitals.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\vitals.py
"""Avainindikaattorien laskenta: tuorein havainto, muutos edelliseen, sparkline-data.

Yhden indikaattorin epäonnistuminen ei kaada muita: virhe tallentuu
``VitalResult.error``-kenttään, ja laatta näyttää "Ei saatavilla".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from data_fetchers import fetch_series
from indicators import Vital

__all__ = ["VitalResult", "compute_vital", "compute_vitals"]


@dataclass
class VitalResult:
    vital: Vital
    value: float | None = None
    date: pd.Timestamp | None = None
    previous: float | None = None
    change: float | None = None
    spark: list[float] = field(default_factory=list)
    geo_used: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.value is not None


def _change(kind: str, value: float, previous: float | None) -> float | None:
    if previous is None or kind == "none":
        return None
    if kind == "diff":
        return value - previous
    if kind == "pct":
        return None if previous == 0 else (value / previous - 1.0) * 100.0
    raise ValueError(f"Tuntematon muutostyyppi: {kind!r}")


def compute_vital(
    v: Vital,
    *,
    today: pd.Timestamp,
    fetch: Callable[..., pd.DataFrame] = fetch_series,
    fetch_kwargs: Mapping[str, Mapping[str, Any]] | None = None,
) -> VitalResult:
    start = today - pd.DateOffset(months=v.lookback_months)
    kwargs = dict((fetch_kwargs or {}).get(v.source, {}))
    errors: list[str] = []
    for spec in v.candidates:
        who = spec.geo or spec.source_code
        try:
            df = fetch(v.source, [spec], start=start, **kwargs)
        except Exception as exc:  # yksi virhe ei saa kaataa koko sivua
            errors.append(f"{who}: {type(exc).__name__}: {exc}")
            continue
        s = df.iloc[:, 0].dropna()
        if s.empty:
            errors.append(f"{who}: ei havaintoja")
            continue
        value = float(s.iloc[-1])
        previous = float(s.iloc[-2]) if len(s) > 1 else None
        return VitalResult(
            vital=v,
            value=value,
            date=s.index[-1],
            previous=previous,
            change=_change(v.change, value, previous),
            spark=[float(x) for x in s.iloc[-v.spark_points:]],
            geo_used=spec.geo,
        )
    return VitalResult(vital=v, error=" | ".join(errors)[:600])


def compute_vitals(
    vitals: Sequence[Vital],
    *,
    today: pd.Timestamp | None = None,
    fetch: Callable[..., pd.DataFrame] = fetch_series,
    fetch_kwargs: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[VitalResult]:
    today = today if today is not None else pd.Timestamp.today().normalize()
    return [compute_vital(v, today=today, fetch=fetch, fetch_kwargs=fetch_kwargs) for v in vitals]
