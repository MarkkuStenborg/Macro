# ============================================================================
# File: macro_dashboard/data_fetchers/worldbank_fetcher.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\worldbank_fetcher.py
"""Maailmanpankin hakija (World Development Indicators, API v2). Ei API-avainta.

``SeriesSpec``:
* ``source_code`` : indikaattorin koodi, esim. ``"BN.CAB.XOKA.GD.ZS"`` (vaihtotase, % BKT:sta)
* ``geo``         : maa- tai aluekoodi, esim. ``"FIN"``, ``"DEU"``, ``"EMU"`` (euroalue), ``"WLD"``

Data on vuosisarja (``Frequency.ANNUAL``); vuosi tallennetaan vuoden alkuhetkeen.
Viimeisin vuosi on tyypillisesti 1-2 vuotta vanha.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import register
from ._http import HttpClient
from .base import BaseFetcher, FetchError, FetchRequest, SchemaError, SeriesSpec

BASE_URL = "https://api.worldbank.org/v2"


@register
class WorldBankFetcher(BaseFetcher):
    source_name = "worldbank"

    def __init__(self, http: HttpClient | None = None, base_url: str = BASE_URL) -> None:
        self._http = http or HttpClient()
        self._base_url = base_url.rstrip("/")

    def get_metadata(self, source_code: str) -> SeriesSpec:
        raise NotImplementedError("Maailmanpankin metadatahaku toteutetaan myöhemmin.")

    def _fetch_raw(self, request: FetchRequest) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for spec in request.series:
            if not spec.geo:
                raise FetchError(f"{spec.series_id}: geo (maakoodi) puuttuu")
            params: dict[str, Any] = {"format": "json", "per_page": 500}
            if request.start is not None or request.end is not None:
                y0 = request.start.year if request.start is not None else 1960
                y1 = request.end.year if request.end is not None else pd.Timestamp.today().year
                params["date"] = f"{y0}:{y1}"
            url = f"{self._base_url}/country/{spec.geo}/indicator/{spec.source_code}"
            resp = self._http.get(url, params=params)
            if resp.status_code != 200:
                raise FetchError(f"{spec.series_id}: Maailmanpankki vastasi HTTP {resp.status_code}: {resp.text[:300]}")
            try:
                payload = resp.json()
            except ValueError as exc:
                raise FetchError(f"{spec.series_id}: vastaus ei ollut JSON-muotoinen") from exc
            # Virhe: [{"message": [{"id": "120", "key": "Invalid value", ...}]}]
            if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
                msg = payload[0].get("message") if isinstance(payload, list) and payload and isinstance(payload[0], dict) else payload
                raise FetchError(f"{spec.series_id}: Maailmanpankki ei palauttanut dataa: {str(msg)[:300]}")
            out[spec.series_id] = payload[1]
        return out

    def _to_canonical(self, raw: dict[str, list[dict[str, Any]]], request: FetchRequest) -> pd.DataFrame:
        cols: dict[str, pd.Series] = {}
        for spec in request.series:
            rows = [r for r in raw[spec.series_id] if r.get("value") is not None]
            if any("date" not in r for r in rows):
                raise SchemaError(f"{spec.series_id}: havainnoista puuttuu 'date'")
            idx = pd.DatetimeIndex(pd.to_datetime([f"{r['date']}-01-01" for r in rows]))
            vals = pd.to_numeric([r["value"] for r in rows], errors="coerce")
            cols[spec.series_id] = pd.Series(vals, index=idx, dtype="float64").sort_index()
        return pd.DataFrame(cols)
