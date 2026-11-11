# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\dbnomics_fetcher.py
"""DBnomics-hakija (api.db.nomics.world). Ei API-avainta.

DBnomics peilaa satoja virallisia lähteitä yhden rajapinnan taakse, mm. Japanin tilastokeskus
(``STATJP``), Cabinet Office (``ESRI``), Kiinan NBS (``NBS``), IMF, OECD ja UNIDO. Peilit päivittyvät
yleensä vuorokauden sisällä, mutta viive lähteestä on mahdollinen; tarkista tuoreus ``--check``-ajolla.

``SeriesSpec``:
* ``source_code`` : ``"PALVELUNTARJOAJA/AINEISTO/SARJA"``, esim. ``"STATJP/CPIm/<sarjakoodi>"``.
  Sarjakoodit löytyvät komennolla ``python probe.py dbn-series STATJP/CPIm "all items"``.
* ``frequency``   : sarjan taajuus (käytetään vain, jos vastauksessa ei ole ``period_start_day``).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import register
from ._http import HttpClient
from ._time import parse_time_labels
from .base import BaseFetcher, FetchError, FetchRequest, SchemaError, SeriesSpec

BASE_URL = "https://api.db.nomics.world/v22"


@register
class DbnomicsFetcher(BaseFetcher):
    source_name = "dbnomics"

    def __init__(self, http: HttpClient | None = None, base_url: str = BASE_URL) -> None:
        self._http = http or HttpClient()
        self._base_url = base_url.rstrip("/")

    def get_metadata(self, source_code: str) -> SeriesSpec:
        raise NotImplementedError("DBnomicsin metadatahaku toteutetaan myöhemmin.")

    def _fetch_raw(self, request: FetchRequest) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for spec in request.series:
            parts = spec.source_code.split("/", 2)
            if len(parts) != 3 or not all(parts):
                raise FetchError(f"{spec.series_id}: source_code pitää olla muotoa PALVELUNTARJOAJA/AINEISTO/SARJA")
            url = f"{self._base_url}/series/{parts[0]}/{parts[1]}/{parts[2]}"
            resp = self._http.get(url, params={"observations": 1, "format": "json"})
            if resp.status_code != 200:
                raise FetchError(f"{spec.series_id}: DBnomics vastasi HTTP {resp.status_code}: {resp.text[:300]}")
            try:
                payload = resp.json()
            except ValueError as exc:
                raise FetchError(f"{spec.series_id}: vastaus ei ollut JSON-muotoinen") from exc
            docs = (payload.get("series") or {}).get("docs") or []
            if not docs:
                raise FetchError(f"{spec.series_id}: DBnomics ei palauttanut sarjaa {spec.source_code}")
            out[spec.series_id] = docs[0]
        return out

    def _to_canonical(self, raw: dict[str, dict[str, Any]], request: FetchRequest) -> pd.DataFrame:
        cols: dict[str, pd.Series] = {}
        for spec in request.series:
            doc = raw[spec.series_id]
            values = doc.get("value")
            if values is None:
                raise SchemaError(f"{spec.series_id}: vastauksesta puuttuu 'value'")
            if doc.get("period_start_day"):
                idx = pd.DatetimeIndex(pd.to_datetime(doc["period_start_day"]))
            elif doc.get("period"):
                idx = parse_time_labels(doc["period"], spec.frequency)
            else:
                raise SchemaError(f"{spec.series_id}: vastauksesta puuttuu 'period'")
            if len(idx) != len(values):
                raise SchemaError(f"{spec.series_id}: jaksoja {len(idx)} mutta arvoja {len(values)}")
            vals = pd.to_numeric(pd.Series(list(values), dtype="object").replace("NA", None), errors="coerce")
            s = pd.Series(vals.to_numpy(dtype="float64"), index=idx).dropna().sort_index()
            cols[spec.series_id] = s[~s.index.duplicated(keep="last")]
        return pd.DataFrame(cols)
