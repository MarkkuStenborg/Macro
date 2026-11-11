# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\suomenpankki_fetcher.py
"""Suomen Pankin viitelainojen tuotot (päivädata), raportin CSV-vienti.

Raportti: "Yields on Finnish benchmark government bonds" (Suomen Pankki), katselusivu
https://reports.suomenpankki.fi/WebForms/ReportViewerPage.aspx?report=%2Ftilastot%2Farvopaperimarkkinat%2Fvelkapaperit%2Fviitelainojen_korot_v2_en&output=
Tuotot lasketaan LSEG:n datasta ensisijaisten jälleenmyyjien keskimääräisistä
myyntihinnoista klo 13.00 ja taulukko päivittyy noin klo 15.50 Suomen aikaa.

CSV-rakenne (varmennettu käyttäjän lataamasta näytteestä): alussa selitysteksti,
sen jälkeen otsikkorivi ``txtb_row_title,title,txtb_currency,txtb_value``;
``title`` = päivä (d.m.yyyy), ``txtb_currency`` = sarjan nimi, esim.
``Yield on goverment bonds, 10 year`` (kirjoitusvirhe "goverment" sallitaan),
``txtb_value`` = tuotto prosentteina. Vienti sisältää oletuksena vain muutaman
viimeisimmän päivän; riittää tuoreimman arvon ja päivämuutoksen laskemiseen.

LÄHDE (järjestyksessä):
1. ``csv_path`` tai ympäristömuuttuja ``SUOMENPANKKI_CSV``: käsin ladattu CSV
   (raportin Export-valikko -> "CSV (comma delimited)"). Tiedoston päivämäärät
   näkyvät sivun solussa, joten vanhentunut tiedosto huomataan.
2. ``export_url`` tai ``SUOMENPANKKI_EXPORT_URL``: suora CSV-latausosoite, jos sellainen
   löytyy. Arvattu SSRS-osoite (``.../ReportServer?...&rs:Format=CSV``) antoi 404
   (ajo 6.11.2026), joten oletusosoitetta ei ole.

``SeriesSpec``:
* ``extra["maturity_years"]`` : laina-aika vuosina, esim. ``10`` (tai ``5``)
"""

from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd

from . import register
from ._http import HttpClient
from .base import BaseFetcher, FetchError, FetchRequest, SchemaError, SeriesSpec

_LABEL = re.compile(r"^\s*yield on gover\w*ment bonds,\s*(\d+)\s*year", re.IGNORECASE)
_REQUIRED = {"title", "txtb_currency", "txtb_value"}


def _maturity(label: str) -> int | None:
    m = _LABEL.match(label or "")
    return int(m.group(1)) if m else None


@register
class SuomenPankkiFetcher(BaseFetcher):
    source_name = "suomenpankki"

    def __init__(
        self,
        http: HttpClient | None = None,
        export_url: str | None = None,
        csv_path: str | Path | None = None,
    ) -> None:
        self._http = http or HttpClient(min_interval=1.0)
        self._export_url = export_url or os.environ.get("SUOMENPANKKI_EXPORT_URL")
        csv_env = os.environ.get("SUOMENPANKKI_CSV")
        self._csv_path = Path(csv_path) if csv_path else (Path(csv_env) if csv_env else None)

    def get_metadata(self, source_code: str) -> SeriesSpec:
        raise NotImplementedError("Suomen Pankin metadatahaku ei ole käytössä.")

    # -- lataus -----------------------------------------------------------

    def _load_text(self) -> str:
        if self._csv_path is not None:
            try:
                data = self._csv_path.read_bytes()
            except FileNotFoundError:
                raise FetchError(
                    f"Suomen Pankin CSV puuttuu: {self._csv_path}. Avaa raportin katselusivu, "
                    "valitse Export -> 'CSV (comma delimited)' ja tallenna tiedosto tähän polkuun."
                ) from None
            except OSError as exc:
                raise FetchError(f"CSV-tiedoston luku epäonnistui ({self._csv_path}): {exc}") from exc
            try:
                return data.decode("utf-8-sig")
            except UnicodeDecodeError:
                return data.decode("cp1252")
        if self._export_url:
            resp = self._http.get(self._export_url)
            if resp.status_code != 200:
                raise FetchError(
                    f"Suomen Pankki vastasi HTTP {resp.status_code} osoitteesta {self._export_url}: "
                    f"{resp.text[:200]!r}. Käytä käsin ladattua CSV:tä (SUOMENPANKKI_CSV / csv_path)."
                )
            return resp.text
        raise FetchError(
            "Suomen Pankin lähdettä ei ole määritelty: anna csv_path (tai SUOMENPANKKI_CSV) "
            "tai export_url (tai SUOMENPANKKI_EXPORT_URL)."
        )

    def _fetch_raw(self, request: FetchRequest) -> dict[str, str]:
        text = self._load_text()  # yksi CSV kattaa kaikki sarjat
        return {s.series_id: text for s in request.series}

    # -- jäsennys ---------------------------------------------------------

    @staticmethod
    def _table(text: str, series_id: str) -> pd.DataFrame:
        lines = text.lstrip("\ufeff").splitlines()
        start = next((i for i, ln in enumerate(lines) if ln.strip().startswith("txtb_row_title")), None)
        if start is None:
            raise SchemaError(
                f"{series_id}: CSV-otsikkoriviä 'txtb_row_title' ei löytynyt "
                f"(onko tiedosto raportin CSV-vienti?); alku: {text[:200]!r}"
            )
        df = pd.read_csv(io.StringIO("\n".join(lines[start:])), dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        missing = _REQUIRED - set(df.columns)
        if missing:
            raise SchemaError(f"{series_id}: CSV:stä puuttuu sarakkeet {sorted(missing)}; on {list(df.columns)}")
        return df

    def _to_canonical(self, raw: dict[str, str], request: FetchRequest) -> pd.DataFrame:
        cols: dict[str, pd.Series] = {}
        for spec in request.series:
            years = spec.extra.get("maturity_years")
            if years is None:
                raise FetchError(f"{spec.series_id}: extra['maturity_years'] puuttuu")
            df = self._table(raw[spec.series_id], spec.series_id)
            sub = df[df["txtb_currency"].map(_maturity) == int(years)]
            if sub.empty:
                have = sorted({str(x) for x in df["txtb_currency"].dropna()})[:5]
                raise SchemaError(
                    f"{spec.series_id}: riviä '{years} year' ei löytynyt; esimerkkejä riveistä: {have}"
                )
            dates = pd.to_datetime(sub["title"].str.strip(), format="%d.%m.%Y", errors="coerce")
            if dates.isna().any():
                bad = sub.loc[dates.isna(), "title"].head(3).tolist()
                raise SchemaError(f"{spec.series_id}: päivämäärää ei voitu jäsentää: {bad}")
            if dates.duplicated().any():
                raise SchemaError(f"{spec.series_id}: samalle päivälle useita rivejä")
            vals = pd.to_numeric(
                sub["txtb_value"].str.strip().str.replace(",", ".", regex=False), errors="coerce"
            )
            cols[spec.series_id] = pd.Series(vals.to_numpy(dtype="float64"), index=pd.DatetimeIndex(dates))
        return pd.DataFrame(cols)
