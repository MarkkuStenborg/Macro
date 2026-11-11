# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\oecd_fetcher.py
"""OECD-hakija (SDMX-REST, ``sdmx.oecd.org``, SDMX-CSV).

OECD:n käyttörajat (voimassa marraskuusta 2024, OECD:n API-ohje):
20 kyselyä minuutissa ja 20 datalatausta tunnissa; ylitys johtaa väliaikaiseen
estoon. Siksi oletuksena kutsuväli on 3,2 s ja vastaukset kannattaa välimuistittaa
(``HttpClient(cache_dir=..., ttl_seconds=86400, min_interval=3.2)``).
Ei API-avainta.

``SeriesSpec``:
* ``source_code``   : dataflow-viite ``"AGENCY,DATAFLOW,VERSIO"`` tai ``"AGENCY,DATAFLOW"``
* ``extra["key"]``  : dimensioavain pisteillä erotettuna; tyhjä osa = kaikki arvot
                      (avaimen on rajattava tasan yhteen sarjaan)

Dataflow-tunnisteet ja dimensioiden järjestys: OECD Data Explorer
(data-explorer.oecd.org), valikko "Developer API".
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from . import register
from ._http import HttpClient
from ._time import parse_time_labels, period_str
from .base import BaseFetcher, FetchError, FetchRequest, SchemaError, SeriesSpec

BASE_URL = "https://sdmx.oecd.org/public/rest"
CSV_ACCEPT = "application/vnd.sdmx.data+csv;version=2.0"


@register
class OecdFetcher(BaseFetcher):
    source_name = "oecd"

    def __init__(self, http: HttpClient | None = None, base_url: str = BASE_URL) -> None:
        self._http = http or HttpClient(min_interval=3.2, ttl_seconds=86400.0)
        self._base_url = base_url.rstrip("/")

    def get_metadata(self, source_code: str) -> SeriesSpec:
        raise NotImplementedError("OECD-metadatahaku (dataflow/DSD) toteutetaan myöhemmin.")

    def _fetch_raw(self, request: FetchRequest) -> dict[str, str]:
        freq = request.frequency
        out: dict[str, str] = {}
        for spec in request.series:
            key = spec.extra.get("key")
            if not key:
                raise FetchError(f"{spec.series_id}: extra['key'] (dimensioavain) puuttuu")
            params: dict[str, str] = {}
            if request.start is not None:
                params["startPeriod"] = period_str(request.start, freq)
            if request.end is not None:
                params["endPeriod"] = period_str(request.end, freq)
            url = f"{self._base_url}/data/{spec.source_code}/{key}"
            resp = self._http.get(url, params=params, headers={"Accept": CSV_ACCEPT})
            if resp.status_code != 200:
                raise FetchError(
                    f"{spec.series_id}: OECD vastasi HTTP {resp.status_code}: {resp.text[:300]}"
                )
            out[spec.series_id] = resp.text
        return out

    def _to_canonical(self, raw: dict[str, str], request: FetchRequest) -> pd.DataFrame:
        freq = request.frequency
        cols: dict[str, pd.Series] = {}
        for spec in request.series:
            df = pd.read_csv(io.StringIO(raw[spec.series_id]), dtype={"TIME_PERIOD": str})
            missing = {"TIME_PERIOD", "OBS_VALUE"} - set(df.columns)
            if missing:
                raise SchemaError(f"{spec.series_id}: CSV:stä puuttuu sarakkeet {sorted(missing)}")
            if df["TIME_PERIOD"].duplicated().any():
                raise SchemaError(
                    f"{spec.series_id}: avain täsmää useaan sarjaan; rajaa extra['key'] tarkemmaksi"
                )
            idx = parse_time_labels(df["TIME_PERIOD"].tolist(), freq)
            vals = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
            cols[spec.series_id] = pd.Series(vals.to_numpy(dtype="float64"), index=idx)
        return pd.DataFrame(cols)
