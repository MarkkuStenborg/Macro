# ============================================================================
# File: macro_dashboard/tests/test_vitals_offline.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\tests\test_vitals_offline.py
"""Offline-testi avainindikaattoreille. Data on TEKAISTUA (satunnaiskulku),
joten testi tarkistaa vain laskennan, varakoodipolut, virheiden eristyksen ja HTML:n.
Aja kansiosta macro_dashboard:  python -m tests.test_vitals_offline
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data_fetchers import FetchError, Frequency
from exporters.vitals_html import format_date, format_number, render_vitals
from indicators import VITALS
from vitals import compute_vitals

TODAY = pd.Timestamp("2026-11-05")
_FREQ = {Frequency.MONTHLY: "MS", Frequency.QUARTERLY: "QS", Frequency.ANNUAL: "YS", Frequency.DAILY: "D"}
BAD_DATASET = "viitelainojen_korot_v2_en"  # simuloi kokonaan epäonnistuvaa hakua (Suomen 10 v tuotto)
BAD_GEO = "EA"  # simuloi euroalueen koodia, jota Eurostat ei tunne (kokeillaan seuraavaa)


def fake_fetch(source, specs, start=None, end=None, **kw):
    spec = specs[0]
    if spec.source_code == BAD_DATASET:
        raise FetchError(f"{spec.geo}: Eurostat vastasi HTTP 400: tekaistu virhe")
    if spec.geo == BAD_GEO:
        raise FetchError("EA: HTTP 400 tuntematon geo")
    rng = np.random.default_rng(abs(hash(spec.series_id)) % 2**32)
    idx = pd.date_range(start, TODAY, freq=_FREQ[spec.frequency])
    base = 5000.0 if spec.source_code == "SP500" else 3.0
    vals = base + np.cumsum(rng.normal(0, base * 0.01, len(idx)))
    df = pd.DataFrame({spec.series_id: vals}, index=idx)
    df.index.name = "date"
    return df


def main() -> None:
    results = compute_vitals(VITALS, today=TODAY, fetch=fake_fetch)
    by_key = {r.vital.key: r for r in results}

    # euroalue: EA epäonnistuu, EA21 onnistuu
    assert by_key["EA.unemployment"].ok and by_key["EA.unemployment"].geo_used == "EA21"
    assert by_key["FI.unemployment"].geo_used == "FI"
    # kokonaan epäonnistuva: eristetty, virhe tallessa, muut ehjiä
    assert not by_key["FI.yield10y"].ok and "tekaistu virhe" in by_key["FI.yield10y"].error
    de = by_key["DE.yield10y"]  # Saksa: päivädata Bundesbankilta
    assert de.ok and de.vital.frequency is Frequency.DAILY and de.vital.source == "bundesbank"
    assert sum(r.ok for r in results) == len(results) - 1
    # muutoslaskenta
    sp = by_key["US.sp500"]
    assert abs(sp.change - (sp.value / sp.previous - 1) * 100) < 1e-9
    u = by_key["FI.unemployment"]
    assert abs(u.change - (u.value - u.previous)) < 1e-9 and len(u.spark) == 24
    assert by_key["EA.policy_rate"].change is None

    # muotoilu
    assert format_number(1234.5, 1) == "1\u00a0234,5"
    assert format_number(-0.04, 1, signed=True) == "\u00b10,0"
    assert format_number(0.25, 1, signed=True).startswith("+")
    assert format_date(pd.Timestamp("2026-09-01"), Frequency.MONTHLY) == "9/2026"
    assert format_date(pd.Timestamp("2026-04-01"), Frequency.QUARTERLY) == "2026 Q2"
    assert format_date(pd.Timestamp("2026-11-05"), Frequency.DAILY) == "5.11.2026"

    html = render_vitals(results)
    assert html.count('class="vt-cell') == len(results) + (-len(results)) % 4  # + täytesolut
    assert html.count('class="vt-cell vt-na"') == 1 and "Ei saatavilla" in html
    assert "S&amp;P 500" in html and "Verdana" in html
    assert "<polyline" not in html and "<polyline" in render_vitals(results, sparklines=True)
    assert "<script" not in html  # ei JavaScriptiä
    # väri vain S&P 500:n muutokselle
    assert html.count("vt-up") + html.count("vt-down") == 2 + 1  # CSS-säännöt + yksi solu

    print(f"OK: {sum(r.ok for r in results)}/{len(results)} solua")


if __name__ == "__main__":
    main()
