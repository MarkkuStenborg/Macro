# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\fred_fetcher.py
"""FRED-hakija (St. Louis Fed, ``fred/series/observations``).

Vaatii ilmaisen API-avaimen: ``api_key``-parametri tai ympäristömuuttuja
``FRED_API_KEY``. Avain ei tallennu välimuistiin eikä virheviesteihin.

``SeriesSpec``:
* ``source_code``      : FRED-sarjatunnus, esim. ``"UNRATE"``
* ``extra["params"]``  : valinnaiset FRED-parametrit (``units``, ``frequency``,
  ``aggregation_method`` jne.)

FRED merkitsee puuttuvan arvon pisteellä (``"."``); se muuttuu ``NaN``iksi.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

from . import register
from ._http import HttpClient
from .base import BaseFetcher, FetchError, FetcherError, FetchRequest, SchemaError, SeriesSpec

BASE_URL = "https://api.stlouisfed.org/fred"


@register
class FredFetcher(BaseFetcher):
    source_name = "fred"

    def __init__(
        self,
        api_key: str | None = None,
        http: HttpClient | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        self._api_key = api_key or os.environ.get("FRED_API_KEY")
        if not self._api_key:
            raise FetcherError(
                "FRED-API-avain puuttuu: anna api_key tai aseta ympäristömuuttuja FRED_API_KEY"
            )
        self._http = http or HttpClient()
        self._base_url = base_url.rstrip("/")

    def get_metadata(self, source_code: str) -> SeriesSpec:
        raise NotImplementedError("FRED-metadatahaku (fred/series) toteutetaan myöhemmin.")

    def _fetch_raw(self, request: FetchRequest) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for spec in request.series:
            params: dict[str, Any] = {
                "series_id": spec.source_code,
                "api_key": self._api_key,
                "file_type": "json",
                **spec.extra.get("params", {}),
            }
            if request.start is not None:
                params["observation_start"] = request.start.strftime("%Y-%m-%d")
            if request.end is not None:
                params["observation_end"] = request.end.strftime("%Y-%m-%d")
            resp = self._http.get(f"{self._base_url}/series/observations", params=params)
            if resp.status_code != 200:
                raise FetchError(
                    f"{spec.series_id}: FRED vastasi HTTP {resp.status_code}: {resp.text[:300]}"
                )
            try:
                out[spec.series_id] = resp.json()
            except ValueError as exc:
                raise FetchError(f"{spec.series_id}: vastaus ei ollut JSON-muotoinen") from exc
        return out

    def _to_canonical(self, raw: dict[str, dict[str, Any]], request: FetchRequest) -> pd.DataFrame:
        cols: dict[str, pd.Series] = {}
        for spec in request.series:
            obs = raw[spec.series_id].get("observations")
            if obs is None:
                raise SchemaError(f"{spec.series_id}: vastauksessa ei ole 'observations'-kenttää")
            idx = pd.DatetimeIndex(pd.to_datetime([o["date"] for o in obs]))
            vals = pd.to_numeric([o["value"] for o in obs], errors="coerce")  # "." -> NaN
            cols[spec.series_id] = pd.Series(vals, index=idx, dtype="float64")
        return pd.DataFrame(cols)
