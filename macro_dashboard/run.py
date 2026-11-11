# ============================================================================
# File: macro_dashboard/run.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\run.py
"""Hae data, laske avainindikaattorit, sovella Macrobond-tyyli ja tallenna output/index.html.

Aja kansiosta macro_dashboard:  python run.py
FRED vaatii ympäristömuuttujan FRED_API_KEY (ks. set_fred_key.py).
"""

from __future__ import annotations

import plotly.graph_objects as go

import config
from data_fetchers import Frequency, HttpClient, SeriesSpec, fetch_series
from exporters.html_generator import save_html
from exporters.vitals_html import render_vitals
from indicators import VITALS
from visualization.macrobond_theme import apply_macrobond_style
from vitals import compute_vitals

# Eurostat une_rt_m: kuukausittainen työttömyysaste, kausitasoitettu, % työvoimasta
_UNE_FILTERS = {"s_adj": "SA", "age": "TOTAL", "unit": "PC_ACT", "sex": "T"}

SERIES = [
    SeriesSpec(
        series_id="FI.unemployment_rate.m",
        source_code="une_rt_m",
        frequency=Frequency.MONTHLY,
        geo="FI",
        unit="% työvoimasta",
        seasonal_adjustment="SA",
        extra={"filters": {**_UNE_FILTERS, "geo": "FI"}},
    ),
    SeriesSpec(
        series_id="EU27.unemployment_rate.m",
        source_code="une_rt_m",
        frequency=Frequency.MONTHLY,
        geo="EU27_2020",
        unit="% työvoimasta",
        seasonal_adjustment="SA",
        extra={"filters": {**_UNE_FILTERS, "geo": "EU27_2020"}},
    ),
]

LABELS = {"FI.unemployment_rate.m": "Suomi", "EU27.unemployment_rate.m": "EU27"}


def build_figure(df) -> go.Figure:
    fig = go.Figure(
        [go.Scatter(x=df.index, y=df[col], name=LABELS[col], mode="lines") for col in df.columns]
    )
    return apply_macrobond_style(
        fig,
        title="Työttömyysaste",
        subtitle="% työvoimasta, kausitasoitettu",
        source="Eurostat (une_rt_m)",
        left_title="%",
    )


def main() -> None:
    # Avainindikaattorit sivun alkuun; FRED-vastaukset välimuistiin tunniksi
    def cached() -> HttpClient:
        return HttpClient(cache_dir=config.CACHE_DIR, ttl_seconds=3600)

    results = compute_vitals(
        VITALS,
        fetch_kwargs={
            "fred": {"http": cached()},
            "bundesbank": {"http": cached()},
            "suomenpankki": {"csv_path": config.BOF_CSV},
        },
    )
    failed = [r for r in results if not r.ok]
    print(f"Avainindikaattorit: {len(results) - len(failed)}/{len(results)} haettu")
    for r in failed:
        print(f"  [EI SAATAVILLA] {r.vital.region} / {r.vital.label}: {r.error}")

    df = fetch_series("eurostat", SERIES, start="2015-01-01")
    fig = build_figure(df)
    path = save_html(
        config.OUTPUT_DIR / "index.html",
        fig,
        page_title="Talouden indikaattorit",
        heading="Talouden indikaattorit",
        description="Suomi ja euroalue; 10 v tuotto myös Saksasta, osakeindeksi USA:sta. Lähteet: Eurostat, FRED, Bundesbank, Suomen Pankki.",
        top_html=render_vitals(results),
    )
    print(f"Kirjoitettu: {path}  ({len(df)} havaintoa, {df.index.min():%Y-%m} – {df.index.max():%Y-%m})")


if __name__ == "__main__":
    main()
