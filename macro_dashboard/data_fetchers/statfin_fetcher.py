# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\statfin_fetcher.py
"""Tilastokeskuksen hakija (PxWeb API, StatFin-tietokanta, JSON-stat2).

Rekisteröity nimellä ``"statfin"``; ``"tilastokeskus"`` toimii aliaksena.
Ei API-avainta. Yhden kyselyn raja on 100 000 arvoa (muuten HTTP 403).

HUOM: Tilastokeskus muutti PxWeb-rajapintaa 8.6.2026: nelimerkkisten
taulutunnusten tiedostonimet ja TABLEID lyhenivät (``statfin_tyonv_pxt_12tg.px``
-> ``12tg.px``), muuttujille tuli uudet VARIABLECODE-koodit (esim.
``contentscode``, ``timeperiod_y``) ja joidenkin taulujen arvokoodeihin tuli
etuliitteitä. Hae oikeat koodit ``describe_table``-metodilla (tai
PxWeb-selaimesta pxdata.stat.fi) ennen sarjan määrittelyä.
Tietokannan juuriosoite ``BASE_URL`` perustuu Tilastokeskuksen ohjeisiin,
mutta sitä ei ole varmennettu tässä ympäristössä.

``SeriesSpec``:
* ``source_code``        : taulun polku StatFin-juuren alla, esim. ``"tyonv/12tg.px"``
* ``extra["query"]``     : ``{muuttujakoodi: [arvokoodit]}``, yksi arvo per muu
                           muuttuja kuin aika
* ``extra["time_code"]`` : aikamuuttujan koodi (haetaan kaikki ajat; rajaus tehdään jälkikäteen)
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import register
from ._http import HttpClient
from ._jsonstat import decode_jsonstat_series
from .base import BaseFetcher, FetchError, FetchRequest, SeriesSpec

BASE_URL = "https://pxdata.stat.fi/PxWeb/api/v1/fi/StatFin"


@register
class StatFinFetcher(BaseFetcher):
    source_name = "statfin"

    def __init__(self, http: HttpClient | None = None, base_url: str = BASE_URL) -> None:
        self._http = http or HttpClient(min_interval=0.5)
        self._base_url = base_url.rstrip("/")

    def get_metadata(self, source_code: str) -> SeriesSpec:
        raise NotImplementedError("Käytä describe_table(source_code) muuttujakoodien selvittämiseen.")

    def describe_table(self, source_code: str) -> dict[str, Any]:
        """Taulun PxWeb-metadata: ``variables`` (code, text, values, valueTexts, time)."""
        resp = self._http.get(f"{self._base_url}/{source_code}")
        if resp.status_code != 200:
            raise FetchError(f"{source_code}: PxWeb vastasi HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def _fetch_raw(self, request: FetchRequest) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for spec in request.series:
            query = spec.extra.get("query")
            time_code = spec.extra.get("time_code")
            if not query or not time_code:
                raise FetchError(f"{spec.series_id}: extra['query'] ja extra['time_code'] vaaditaan")
            items = [
                {"code": code, "selection": {"filter": "item", "values": list(values)}}
                for code, values in query.items()
                if code != time_code
            ]
            time_values = query.get(time_code)
            items.append(
                {
                    "code": time_code,
                    "selection": (
                        {"filter": "item", "values": list(time_values)}
                        if time_values
                        else {"filter": "all", "values": ["*"]}
                    ),
                }
            )
            body = {"query": items, "response": {"format": "json-stat2"}}
            resp = self._http.post(f"{self._base_url}/{spec.source_code}", json_body=body)
            if resp.status_code != 200:
                hint = ""
                if resp.status_code in (400, 403, 404):
                    hint = (
                        " Tarkista taulun polku ja muuttuja-/arvokoodit (describe_table); "
                        "403 voi myös tarkoittaa yli 100 000 arvon kyselyä. "
                        "Rajapinta muuttui 8.6.2026."
                    )
                raise FetchError(
                    f"{spec.series_id}: PxWeb vastasi HTTP {resp.status_code}: {resp.text[:300]}{hint}"
                )
            try:
                out[spec.series_id] = resp.json()
            except ValueError as exc:
                raise FetchError(f"{spec.series_id}: vastaus ei ollut JSON-muotoinen") from exc
        return out

    def _to_canonical(self, raw: dict[str, dict[str, Any]], request: FetchRequest) -> pd.DataFrame:
        freq = request.frequency
        return pd.DataFrame(
            {
                s.series_id: decode_jsonstat_series(
                    raw[s.series_id], s.series_id, freq, s.extra.get("time_code")
                )
                for s in request.series
            }
        )
