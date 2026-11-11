# ============================================================================
# File: macro_dashboard/data_fetchers/_jsonstat.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\_jsonstat.py
"""JSON-stat 2.0 -dekooderi yhden sarjan vastaukselle (Eurostat, Tilastokeskus/PxWeb)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .base import Frequency, SchemaError
from ._time import parse_time_labels

__all__ = ["decode_jsonstat_series"]


def decode_jsonstat_series(
    payload: dict[str, Any],
    series_id: str,
    freq: Frequency,
    time_dim: str | None = None,
) -> pd.Series:
    """Pura JSON-stat-vastaus ``pd.Series``iksi (indeksinä aika).

    Kaikilla muilla dimensioilla kuin aikadimensiolla on oltava täsmälleen
    yksi arvo (suodattimet rajaavat vastauksen yhteen sarjaan).
    Aikadimension nimi: ``time_dim`` -> ``role.time`` -> ``"time"``.
    """
    ids: list[str] = payload["id"]
    sizes: list[int] = payload["size"]
    if time_dim is None:
        role_time = (payload.get("role") or {}).get("time") or []
        time_dim = role_time[0] if role_time else "time"
    if time_dim not in ids:
        raise SchemaError(f"{series_id}: aikadimensiota {time_dim!r} ei löydy (id={ids})")

    many = {i: n for i, n in zip(ids, sizes) if i != time_dim and n != 1}
    if many:
        raise SchemaError(
            f"{series_id}: suodattimet eivät rajaa yhteen sarjaan, usean arvon dimensiot: {many}"
        )

    time_index = payload["dimension"][time_dim]["category"]["index"]
    if isinstance(time_index, list):  # JSON-stat sallii myös listamuodon
        time_index = {code: pos for pos, code in enumerate(time_index)}
    if len(time_index) != sizes[ids.index(time_dim)]:
        raise SchemaError(f"{series_id}: aikadimension koko ei täsmää")

    values = payload.get("value", {})
    if isinstance(values, list):
        values = {str(i): v for i, v in enumerate(values) if v is not None}

    codes = sorted(time_index, key=time_index.get)
    data = [values.get(str(time_index[c])) for c in codes]
    return pd.Series(data, index=parse_time_labels(codes, freq), dtype="float64", name=series_id)
