# ============================================================================
# File: macro_dashboard/indicators.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\indicators.py
"""Sivun alun avainindikaattorit ("vitals"): Suomi, euroalue, Saksa (10 v tuotto) ja USA:n S&P 500.

Jokainen ``Vital`` määrittelee yhden solun. ``candidates`` on lista
vaihtoehtoisia ``SeriesSpec``ejä, joita kokeillaan järjestyksessä, kunnes
yksi onnistuu. Euroalueelle kokeillaan geo-koodeja ``EURO_AREA_GEOS``
(Eurostat on vaihtanut euroalueen koodia jäsenmäärän kasvaessa).

Solut näytetään ``VITALS``-listan järjestyksessä neljällä sarakkeella, joten
pidä lista 4:n monikertana ja pareina (Suomi, euroalue).

HUOM: koodit ovat kirjoitushetkellä VARMENNETTUJA vain työttömyysasteelle
(Eurostat ``une_rt_m``, FI ja EU27_2020) ja FRED:n ``UNRATE``-sarjalle.
Kaikki muut dataset-, suodatin- ja sarjakoodit ovat arvioita, ja jos jokin
epäonnistuu, solu näyttää "Ei saatavilla" ja ajo tulostaa syyn.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from data_fetchers import Frequency, SeriesSpec

EURO_AREA_GEOS = ("EA", "EA21", "EA20")  # kokeillaan järjestyksessä


@dataclass(frozen=True)
class Vital:
    key: str
    group: str  # ryhmittelyyn tulevaisuudessa; ei näytetä ikkunassa
    label: str  # pitkä nimi (tooltip, diagnostiikka)
    region: str  # "Suomi" | "Euroalue" | "USA"
    source: str  # data_fetchers-rekisterin nimi
    candidates: tuple[SeriesSpec, ...]  # kokeillaan järjestyksessä
    unit: str  # näyttöyksikkö solussa, esim. "%"
    short: str = ""  # lyhyt nimi solun otsikkoon
    decimals: int = 1
    change: Literal["diff", "pct", "none"] = "diff"  # muutos edelliseen havaintoon
    change_decimals: int = 1
    color_change: bool = False  # väritä muutos vihreä/punainen (vain markkinahinnoille)
    lookback_months: int = 36
    spark_points: int = 24

    @property
    def frequency(self) -> Frequency:
        return self.candidates[0].frequency

    @property
    def display_label(self) -> str:
        return self.short or self.label


def _eurostat(
    key: str,
    group: str,
    label: str,
    region: str,
    dataset: str,
    freq: Frequency,
    filters: Mapping[str, str],
    geo_codes: tuple[str, ...],
    **kw,
) -> Vital:
    specs = tuple(
        SeriesSpec(
            series_id=key,
            source_code=dataset,
            frequency=freq,
            geo=g,
            extra={"filters": {**filters, "geo": g}},
        )
        for g in geo_codes
    )
    return Vital(key, group, label, region, "eurostat", specs, **kw)


_M, _Q, _A = Frequency.MONTHLY, Frequency.QUARTERLY, Frequency.ANNUAL
_FI = ("FI",)
_EA = EURO_AREA_GEOS

_GDP = {"s_adj": "SCA", "na_item": "B1GQ"}
_UNE = {"s_adj": "SA", "age": "TOTAL", "unit": "PC_ACT", "sex": "T"}  # varmennettu
_HICP = {"unit": "RCH_A", "coicop": "CP00"}
_GOV = {"unit": "PC_GDP", "sector": "S13"}


def _pair(key, group, label, dataset, freq, filters, **kw):
    return [
        _eurostat(f"FI.{key}", group, label, "Suomi", dataset, freq, filters, _FI, **kw),
        _eurostat(f"EA.{key}", group, label, "Euroalue", dataset, freq, filters, _EA, **kw),
    ]


VITALS: list[Vital] = [
    # --- Kasvu ---
    *_pair("gdp_qoq", "Kasvu", "BKT, muutos edellisestä neljänneksestä", "namq_10_gdp", _Q,
           {**_GDP, "unit": "CLV_PCH_PRE"}, short="BKT q/q", unit="%",
           lookback_months=60, spark_points=12),
    *_pair("gdp_yoy", "Kasvu", "BKT, muutos vuodentakaisesta", "namq_10_gdp", _Q,
           {**_GDP, "unit": "CLV_PCH_SM"}, short="BKT y/y", unit="%",
           lookback_months=60, spark_points=12),
    # --- Työmarkkinat ja hinnat ---
    *_pair("unemployment", "Työmarkkinat", "Työttömyysaste", "une_rt_m", _M, _UNE,
           short="Työttömyysaste", unit="%", lookback_months=36, spark_points=24),
    *_pair("hicp", "Hinnat", "Inflaatio (HICP), vuosimuutos", "prc_hicp_manr", _M, _HICP,
           short="Inflaatio (HICP)", unit="%", lookback_months=36, spark_points=24),
    # --- Rahoitus ---
    Vital(  # päivädata Suomen Pankilta (viitelainan tuotto klo 13.00)
        key="FI.yield10y",
        group="Rahoitus",
        label="10 v valtionlainan tuotto (päivädata, Suomen Pankki)",
        short="10 v tuotto",
        region="Suomi",
        source="suomenpankki",
        candidates=(
            SeriesSpec("FI.yield10y", "viitelainojen_korot_v2_en", Frequency.DAILY, geo="FI",
                       extra={"maturity_years": 10}),
        ),
        unit="%",
        decimals=2,
        change_decimals=2,
        lookback_months=8,
        spark_points=120,
    ),
    Vital(  # päivädata Bundesbankilta (uusimman 10 v Bundin tuotto)
        key="DE.yield10y",
        group="Rahoitus",
        label="10 v valtionlainan tuotto (päivädata, Bundesbank)",
        short="10 v tuotto",
        region="Saksa",
        source="bundesbank",
        candidates=(
            SeriesSpec(
                "DE.yield10y", "BBSSY", Frequency.DAILY, geo="DE",
                extra={"key": "D.REN.EUR.A630.000000WT1010.A"},
            ),
        ),
        unit="%",
        decimals=2,
        change_decimals=2,
        lookback_months=8,
        spark_points=120,
    ),
    Vital(
        key="EA.policy_rate",
        group="Rahoitus",
        label="EKP:n talletuskorko",
        short="EKP talletuskorko",
        region="Euroalue",
        source="fred",
        candidates=(SeriesSpec("EA.policy_rate", "ECBDFR", Frequency.DAILY),),
        unit="%",
        decimals=2,
        change="none",
        lookback_months=8,
        spark_points=120,
    ),
    Vital(
        key="US.sp500",
        group="Rahoitus",
        label="S&P 500",
        short="S&P 500",
        region="USA",
        source="fred",
        candidates=(SeriesSpec("US.sp500", "SP500", Frequency.DAILY),),
        unit="",
        decimals=0,
        change="pct",
        change_decimals=2,
        color_change=True,
        lookback_months=8,
        spark_points=120,
    ),
    # --- Julkinen talous (vuositiedot, viive) ---
    *_pair("gov_balance", "Julkinen talous", "Julkisyhteisöjen rahoitusasema, % BKT",
           "gov_10dd_edpt1", _A, {**_GOV, "na_item": "B9"}, short="Rahoitusasema",
           unit="% BKT:sta", lookback_months=132, spark_points=10),
    *_pair("gov_debt", "Julkinen talous", "Julkisyhteisöjen bruttovelka, % BKT",
           "gov_10dd_edpt1", _A, {**_GOV, "na_item": "GD"}, short="Bruttovelka",
           unit="% BKT:sta", lookback_months=132, spark_points=10),
]
