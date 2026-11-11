# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\tests\test_pipeline_offline.py
"""Offline-testi: Eurostat-hakija -> kanoninen muoto -> Macrobond-tyyli -> HTML.

Käyttää TEKAISTUA JSON-stat-vastausta (ei oikeaa dataa), joten testi tarkistaa
vain putken rakenteen ja jäsennyksen, ei Eurostatin todellista vastausmuotoa.
Aja kansiosta macro_dashboard:  python -m tests.test_pipeline_offline
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pandas as pd

import run
from data_fetchers import fetch_series, get_fetcher
from exporters.html_generator import save_html


class _FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeSession:
    """Palauttaa JSON-stat-vastauksen: 2015-01 ... 2025-12, yksi puuttuva arvo."""

    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params)))
        months = pd.period_range("2015-01", "2025-12", freq="M")
        offset = 0.0 if params["geo"] == "FI" else -1.0
        values = {
            str(i): round(8 + offset + 1.5 * math.sin(i / 9), 2)
            for i in range(len(months))
            if i != 40  # puuttuva havainto -> NaN
        }
        ids = ["freq", "s_adj", "age", "unit", "sex", "geo", "time"]
        return _FakeResponse(
            {
                "version": "2.0",
                "class": "dataset",
                "id": ids,
                "size": [1, 1, 1, 1, 1, 1, len(months)],
                "value": values,
                "dimension": {
                    "time": {"category": {"index": {str(p): i for i, p in enumerate(months)}}}
                },
            }
        )


def main() -> None:
    session = _FakeSession()
    fetcher = get_fetcher("eurostat", session=session)
    from data_fetchers import FetchRequest

    df = fetcher.fetch(FetchRequest(series=run.SERIES, start=pd.Timestamp("2015-01-01")))

    # kanoninen muoto
    assert isinstance(df.index, pd.DatetimeIndex) and df.index.name == "date"
    assert df.index.freqstr == "MS" and df.index.is_monotonic_increasing
    assert list(df.columns) == [s.series_id for s in run.SERIES]
    assert all(str(t) == "float64" for t in df.dtypes)
    assert df.isna().sum().sum() == 2  # yksi puuttuva per sarja
    assert df.attrs["source"] == "eurostat"
    assert len(session.calls) == 2
    assert session.calls[0][1]["sinceTimePeriod"] == "2015-01"

    # fetch_series-sisäänkäynti toimii samoin
    df2 = fetch_series("eurostat", run.SERIES, session=_FakeSession())
    assert df2.shape == df.shape

    # kuvio + HTML
    fig = run.build_figure(df)
    with tempfile.TemporaryDirectory() as tmp:
        out = save_html(Path(tmp) / "index.html", fig, page_title="Testi", heading="Testi")
        text = out.read_text(encoding="utf-8")
    assert "cdn.tailwindcss.com" in text and "plotly" in text.lower()
    # Plotly koodaa ääkköset JSON:iin \uXXXX-muotoon (selain näyttää ne oikein)
    assert "L\\u00e4hde: Eurostat (une_rt_m)" in text
    assert "Ty\\u00f6tt\\u00f6myysaste" in text
    assert text.count("<section") == 1

    print("OK:", df.shape, df.index.min().date(), "–", df.index.max().date())
    print("y2-akseli:", fig.layout.yaxis2.side, fig.layout.yaxis2.matches,
          "| tick-esimerkki:", fig.layout.xaxis.ticktext[:4])


if __name__ == "__main__":
    main()