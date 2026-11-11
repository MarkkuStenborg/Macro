# ============================================================================
# File: macro_dashboard/tests/test_bundesbank_offline.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\tests\test_bundesbank_offline.py
"""Offline-testi Bundesbank-hakijalle TEKAISTUILLA CSV-vastauksilla.

Testaa koodin logiikan (formaatin varavalinta, erottimet, desimaalipilkku, virheet),
ei Bundesbankin todellista vastausmuotoa.
Aja kansiosta macro_dashboard:  python -m tests.test_bundesbank_offline
"""

from __future__ import annotations

import pandas as pd

from data_fetchers import FetchError, FetchRequest, Frequency, HttpClient, SchemaError, SeriesSpec, get_fetcher
from tests.test_fetchers_offline import _Resp, _Session

SPEC = SeriesSpec("DE.yield10y", "BBSSY", Frequency.DAILY, geo="DE",
                  extra={"key": "D.REN.EUR.A630.000000WT1010.A"})

SDMX_CSV = ("KEY,FREQ,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
            "BBSSY.D...,D,2026-11-02,2.61,A\nBBSSY.D...,D,2026-11-03,2.64,A\n"
            "BBSSY.D...,D,2026-11-04,.,A\nBBSSY.D...,D,2026-11-05,2.70,A\n")
GERMAN_CSV = ("\ufeff\"TIME_PERIOD\";\"OBS_VALUE\"\n2026-11-02;2,61\n2026-11-03;2,64\n2026-11-05;2,70\n")


def _fetch(session, spec=SPEC, start="2026-11-01"):
    http = HttpClient(session=session, sleep=lambda s: None)
    f = get_fetcher("bundesbank", http=http)
    return f.fetch(FetchRequest(series=[spec], start=pd.Timestamp(start)))


def main() -> None:
    # tavallinen SDMX-CSV
    s = _Session(_Resp(text=SDMX_CSV))
    df = _fetch(s)
    assert df.index.freqstr == "D" and len(df) == 4 and df.isna().sum().sum() == 1  # 4.11. puuttuu
    assert df.iloc[-1, 0] == 2.70 and df.index[-1] == pd.Timestamp("2026-11-05")
    c = s.calls[0]
    assert c["url"].endswith("/data/BBSSY/D.REN.EUR.A630.000000WT1010.A")
    assert c["params"]["format"] == "sdmx_csv" and c["params"]["startPeriod"] == "2026-11-01"

    # sdmx_csv hylätään -> kokeillaan csv; puolipiste + desimaalipilkku + BOM; viikonloppuaukko -> NaN
    s = _Session(_Resp(400, text="unsupported"), _Resp(text=GERMAN_CSV))
    df = _fetch(s)
    assert [c["params"]["format"] for c in s.calls] == ["sdmx_csv", "csv"]
    assert df.iloc[0, 0] == 2.61 and len(df) == 4 and df.isna().sum().sum() == 1

    # 404 ei kokeile toista formaattia
    s = _Session(_Resp(404, text="not found"))
    try:
        _fetch(s)
        raise AssertionError
    except FetchError as e:
        assert "404" in str(e) and len(s.calls) == 1

    # tuntematon sarakemuoto -> SchemaError, vastauksen alku mukana
    try:
        _fetch(_Session(_Resp(text="Titel;x\nfoo;bar\n")))
        raise AssertionError
    except SchemaError as e:
        assert "Titel" in str(e)

    # avain puuttuu / useaan sarjaan täsmäävä avain
    try:
        _fetch(_Session(_Resp(text=SDMX_CSV)), SeriesSpec("x", "BBSSY", Frequency.DAILY))
        raise AssertionError
    except FetchError:
        pass
    try:
        _fetch(_Session(_Resp(text=SDMX_CSV + "BBSSY.D...,D,2026-11-05,9.9,A\n")))
        raise AssertionError
    except SchemaError:
        pass

    print("OK test_bundesbank_offline")


if __name__ == "__main__":
    main()
