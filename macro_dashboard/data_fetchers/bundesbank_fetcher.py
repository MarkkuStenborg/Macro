# ============================================================================
# File: macro_dashboard/data_fetchers/bundesbank_fetcher.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\bundesbank_fetcher.py
"""Bundesbankin hakija (SDMX Web Service, ``api.statistiken.bundesbank.de``, CSV).

Ei API-avainta. Pyyntö: ``/rest/data/{flow}/{key}?format=sdmx_csv`` (dokumentaation
mukainen arvo); jos palvelin hylkää sen (400/406/415), kokeillaan ``format=csv``
(arvo, jota Bundesbankin omat latauslinkit käyttävät).

``SeriesSpec``:
* ``source_code``   : dataflow, esim. ``"BBSSY"``
* ``extra["key"]``  : sarja-avain, esim. ``"D.REN.EUR.A630.000000WT1010.A"``
                      (Saksan uusimman 10 v valtion lainan päivätuotto)

CSV-jäsennys on tehty dokumentaation perusteella, mutta sitä ei ole ajettu
oikealla vastauksella: sarakkeet tunnistetaan nimestä (TIME_PERIOD/OBS_VALUE),
erotin tunnistetaan automaattisesti ja desimaalipilkku hyväksytään. Jos muoto
poikkeaa, virhe näyttää vastauksen alun.
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from . import register
from ._http import HttpClient
from ._time import parse_time_labels, period_str
from .base import BaseFetcher, FetchError, FetchRequest, SchemaError, SeriesSpec

BASE_URL = "https://api.statistiken.bundesbank.de/rest"
FORMATS = ("sdmx_csv", "csv")
_FALLBACK_STATUS = {400, 406, 415}
_TIME_COLS = ("TIME_PERIOD", "TIME", "DATE")
_VALUE_COLS = ("OBS_VALUE", "VALUE", "OBS")


@register
class BundesbankFetcher(BaseFetcher):
    source_name = "bundesbank"

    def __init__(self, http: HttpClient | None = None, base_url: str = BASE_URL) -> None:
        self._http = http or HttpClient(min_interval=0.5)
        self._base_url = base_url.rstrip("/")

    def get_metadata(self, source_code: str) -> SeriesSpec:
        raise NotImplementedError("Bundesbank-metadatahaku toteutetaan myöhemmin.")

    def _fetch_raw(self, request: FetchRequest) -> dict[str, str]:
        freq = request.frequency
        out: dict[str, str] = {}
        for spec in request.series:
            key = spec.extra.get("key")
            if not key:
                raise FetchError(f"{spec.series_id}: extra['key'] (sarja-avain) puuttuu")
            params: dict[str, str] = {"lang": "en"}
            if request.start is not None:
                params["startPeriod"] = period_str(request.start, freq)
            if request.end is not None:
                params["endPeriod"] = period_str(request.end, freq)
            url = f"{self._base_url}/data/{spec.source_code}/{key}"
            problem = ""
            for fmt in FORMATS:
                resp = self._http.get(url, params={**params, "format": fmt})
                if resp.status_code == 200:
                    out[spec.series_id] = resp.text
                    break
                problem = f"HTTP {resp.status_code}: {resp.text[:300]}"
                if resp.status_code not in _FALLBACK_STATUS:
                    break
            if spec.series_id not in out:
                raise FetchError(f"{spec.series_id}: Bundesbank vastasi {problem}")
        return out

    def _to_canonical(self, raw: dict[str, str], request: FetchRequest) -> pd.DataFrame:
        freq = request.frequency
        cols: dict[str, pd.Series] = {}
        for spec in request.series:
            text = raw[spec.series_id].lstrip("\ufeff")
            try:
                df = pd.read_csv(io.StringIO(text), sep=None, engine="python", dtype=str)
            except Exception as exc:
                raise SchemaError(
                    f"{spec.series_id}: CSV:n jäsennys epäonnistui ({exc}); alku: {text[:200]!r}"
                ) from exc
            upper = {str(c).strip().upper(): c for c in df.columns}
            tcol = next((upper[c] for c in _TIME_COLS if c in upper), None)
            vcol = next((upper[c] for c in _VALUE_COLS if c in upper), None)
            if tcol is None or vcol is None:
                raise SchemaError(
                    f"{spec.series_id}: aika-/arvosarakkeita ei löytynyt; sarakkeet "
                    f"{list(df.columns)[:8]}; alku: {text[:200]!r}"
                )
            if df[tcol].duplicated().any():
                raise SchemaError(
                    f"{spec.series_id}: avain täsmää useaan sarjaan; rajaa extra['key'] tarkemmaksi"
                )
            idx = parse_time_labels(df[tcol].str.strip().tolist(), freq)
            vals = pd.to_numeric(df[vcol].str.strip().str.replace(",", ".", regex=False), errors="coerce")
            cols[spec.series_id] = pd.Series(vals.to_numpy(dtype="float64"), index=idx)
        return pd.DataFrame(cols)
