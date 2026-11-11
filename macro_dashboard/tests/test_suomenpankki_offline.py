# ============================================================================
# File: macro_dashboard/tests/test_suomenpankki_offline.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\tests\test_suomenpankki_offline.py
"""Offline-testi Suomen Pankin hakijalle OIKEALLA CSV-näytteellä (tests/data/).

Näyte on käyttäjän Suomen Pankin raportista lataama CSV-vienti (3.-5.11.2026).
Aja kansiosta macro_dashboard:  python -m tests.test_suomenpankki_offline
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd

from data_fetchers import FetchError, FetchRequest, Frequency, HttpClient, SchemaError, SeriesSpec, get_fetcher
from tests.test_fetchers_offline import _Resp, _Session

SAMPLE = Path(__file__).parent / "data" / "viitelainojen_korot_sample.csv"
TEXT = SAMPLE.read_text(encoding="utf-8")
Y10 = SeriesSpec("FI.yield10y", "viitelainojen_korot_v2_en", Frequency.DAILY, geo="FI",
                 extra={"maturity_years": 10})
Y5 = SeriesSpec("FI.yield5y", "viitelainojen_korot_v2_en", Frequency.DAILY, geo="FI",
                extra={"maturity_years": 5})


def _fetcher(session=None, **kw):
    http = HttpClient(session=session or _Session(_Resp(text=TEXT)), sleep=lambda s: None)
    return get_fetcher("suomenpankki", http=http, **kw)


def _expect(exc_type, fragment, fn):
    try:
        fn()
    except exc_type as e:
        assert fragment in str(e), f"{fragment!r} puuttuu viestistä: {e}"
        return
    raise AssertionError(f"odotettiin {exc_type.__name__}")


def main() -> None:
    for var in ("SUOMENPANKKI_CSV", "SUOMENPANKKI_EXPORT_URL"):
        os.environ.pop(var, None)

    # 1) käsin ladattu CSV: sekä 10 v että 5 v samasta tiedostosta
    df = _fetcher(csv_path=SAMPLE).fetch(FetchRequest(series=[Y10, Y5]))
    assert df.index.freqstr == "D" and list(df.columns) == ["FI.yield10y", "FI.yield5y"]
    assert [d.strftime("%Y-%m-%d") for d in df.index] == ["2026-11-03", "2026-11-04", "2026-11-05"]
    assert df["FI.yield10y"].tolist() == [3.75, 3.73, 3.65]  # tiedoston arvot
    assert df["FI.yield5y"].tolist() == [3.45, 3.44, 3.37]

    # 1b) Windows-1252-koodattu tiedosto (en-viiva) ja BOM-tiedosto
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "cp1252.csv"
        p.write_bytes(TEXT.replace("\u2013", "\x96").encode("cp1252", errors="replace"))
        assert _fetcher(csv_path=p).fetch(FetchRequest(series=[Y10]))["FI.yield10y"].iloc[-1] == 3.65
        p2 = Path(tmp) / "bom.csv"
        p2.write_bytes(b"\xef\xbb\xbf" + TEXT.encode("utf-8"))
        assert _fetcher(csv_path=p2).fetch(FetchRequest(series=[Y10]))["FI.yield10y"].iloc[-1] == 3.65

    # 2) suora latausosoite (export_url) ja start-rajaus
    s = _Session(_Resp(text=TEXT))
    df = _fetcher(s, export_url="https://example.test/x.csv").fetch(
        FetchRequest(series=[Y10], start=pd.Timestamp("2026-11-04")))
    assert s.calls[0]["url"] == "https://example.test/x.csv" and df["FI.yield10y"].tolist() == [3.73, 3.65]

    # 3) virhepolut
    _expect(FetchError, "csv_path", lambda: _fetcher().fetch(FetchRequest(series=[Y10])))  # ei lähdettä
    _expect(FetchError, "Export", lambda: _fetcher(csv_path=SAMPLE.parent / "puuttuu.csv").fetch(
        FetchRequest(series=[Y10])))
    _expect(FetchError, "404", lambda: _fetcher(_Session(_Resp(404, text="Not found")),
            export_url="https://example.test/x.csv").fetch(FetchRequest(series=[Y10])))
    _expect(SchemaError, "txtb_row_title", lambda: _fetcher(
        _Session(_Resp(text="<html><body>Login</body></html>")),
        export_url="https://example.test/x.csv").fetch(FetchRequest(series=[Y10])))
    _expect(SchemaError, "7 year", lambda: _fetcher(csv_path=SAMPLE).fetch(FetchRequest(series=[
        SeriesSpec("x", "r", Frequency.DAILY, extra={"maturity_years": 7})])))
    _expect(FetchError, "maturity_years", lambda: _fetcher(csv_path=SAMPLE).fetch(
        FetchRequest(series=[SeriesSpec("x", "r", Frequency.DAILY)])))

    print("OK test_suomenpankki_offline")


if __name__ == "__main__":
    main()
