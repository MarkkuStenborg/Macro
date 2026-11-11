# ============================================================================
# File: macro_dashboard/data_fetchers/eurostat_fetcher.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\eurostat_fetcher.py
"""Eurostat-hakija (Statistics API, JSON-stat 2.0).

Yksi HTTP-haku per sarja. Sarja määritellään ``SeriesSpec``illä:

* ``source_code``  : Eurostatin datasetin koodi, esim. ``"une_rt_m"``
* ``extra["filters"]`` : dimensiosuodattimet, jotka rajaavat vastauksen yhteen
  sarjaan (kaikilla muilla dimensioilla kuin ``time`` on oltava yksi arvo)

Esimerkki::

    SeriesSpec(
        series_id="FI.unemployment_rate.m",
        source_code="une_rt_m",
        frequency=Frequency.MONTHLY,
        geo="FI",
        unit="% työvoimasta",
        seasonal_adjustment="SA",
        extra={"filters": {"geo": "FI", "s_adj": "SA", "age": "TOTAL",
                           "unit": "PC_ACT", "sex": "T"}},
    )

Ei API-avainta. Suurten kyselyjen vastaus voi hidastua: nosta ``timeout``.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import requests

from . import register
from ._jsonstat import decode_jsonstat_series
from ._time import period_str
from .base import BaseFetcher, FetchError, FetchRequest, SeriesSpec

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


@register
class EurostatFetcher(BaseFetcher):
    source_name = "eurostat"

    def __init__(
        self,
        session: requests.Session | None = None,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        lang: str = "EN",
    ) -> None:
        self._session = session or requests.Session()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._lang = lang

    # -- BaseFetcher ------------------------------------------------------

    def get_metadata(self, source_code: str) -> SeriesSpec:
        raise NotImplementedError(
            "Eurostat-metadatahaku (dataflow/DSD) toteutetaan myöhemmin; "
            "määrittele sarjat SeriesSpecillä."
        )

    def _fetch_raw(self, request: FetchRequest) -> dict[str, dict[str, Any]]:
        """Palauttaa ``{series_id: JSON-stat-vastaus}``."""
        freq = request.frequency
        out: dict[str, dict[str, Any]] = {}
        for spec in request.series:
            filters: Mapping[str, str] = spec.extra.get("filters", {})
            if not filters:
                raise FetchError(
                    f"{spec.series_id}: extra['filters'] puuttuu; "
                    "ilman suodattimia vastaus ei rajaudu yhteen sarjaan"
                )
            params: dict[str, str] = {"format": "JSON", "lang": self._lang, **filters}
            if request.start is not None:
                params["sinceTimePeriod"] = period_str(request.start, freq)
            if request.end is not None:
                params["untilTimePeriod"] = period_str(request.end, freq)
            url = f"{self._base_url}/{spec.source_code}"
            try:
                resp = self._session.get(url, params=params, timeout=self._timeout)
            except requests.RequestException as exc:
                raise FetchError(f"{spec.series_id}: yhteys Eurostatiin epäonnistui: {exc}") from exc
            if resp.status_code != 200:
                raise FetchError(
                    f"{spec.series_id}: Eurostat vastasi HTTP {resp.status_code}: {resp.text[:300]}"
                )
            try:
                payload = resp.json()
            except ValueError as exc:
                raise FetchError(f"{spec.series_id}: vastaus ei ollut JSON-muotoinen") from exc
            if "error" in payload:
                raise FetchError(f"{spec.series_id}: Eurostat-virhe: {payload['error']}")
            out[spec.series_id] = payload
        return out

    def _to_canonical(self, raw: dict[str, dict[str, Any]], request: FetchRequest) -> pd.DataFrame:
        freq = request.frequency
        return pd.DataFrame(
            {s.series_id: decode_jsonstat_series(raw[s.series_id], s.series_id, freq, "time")
             for s in request.series}
        )
