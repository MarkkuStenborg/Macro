# ============================================================================
# File: macro_dashboard/tests/test_fetchers_offline.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\tests\test_fetchers_offline.py
"""Offline-testit FRED-, OECD-, Tilastokeskus- ja IMF-hakijoille sekä HttpClientille.

Kaikki vastaukset ovat TEKAISTUJA ja kirjoitettu käsitykseni mukaan kunkin
rajapinnan muodosta. Testit varmistavat koodin logiikan (jäsennys, välimuisti,
avaimen suojaus, virheet), eivät rajapintojen todellista toimintaa.
Aja kansiosta macro_dashboard:  python -m tests.test_fetchers_offline
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import requests

from data_fetchers import (
    FetcherError,
    FetchError,
    FetchRequest,
    Frequency,
    HttpClient,
    SchemaError,
    SeriesSpec,
    get_fetcher,
)

SECRET = "SECRETKEY123"


class _Resp:
    def __init__(self, status=200, payload=None, text=None, headers=None):
        self.status_code = status
        self.text = text if text is not None else json.dumps(payload)
        self.headers = headers or {}

    def json(self):
        return json.loads(self.text)


class _Session:
    """Palauttaa jonosta vastaukset järjestyksessä; kirjaa kutsut."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def request(self, method, url, params=None, headers=None, json=None, timeout=None):
        self.calls.append(dict(method=method, url=url, params=params, headers=headers, json=json))
        r = self.responses[0] if len(self.responses) == 1 else self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _http(session, **kw):
    return HttpClient(session=session, sleep=lambda s: None, **kw)


def _req(spec, start=None):
    return FetchRequest(series=[spec], start=pd.Timestamp(start) if start else None)


def _check_canonical(df, n, nan=0):
    assert df.index.name == "date" and df.index.freqstr == "MS" and len(df) == n
    assert str(df.iloc[:, 0].dtype) == "float64" and int(df.isna().sum().sum()) == nan


# --- FRED -----------------------------------------------------------------
def test_fred():
    payload = {"observations": [
        {"date": "2024-01-01", "value": "3.7"},
        {"date": "2024-02-01", "value": "."},
        {"date": "2024-03-01", "value": "3.8"},
    ]}
    spec = SeriesSpec("US.unrate.m", "UNRATE", Frequency.MONTHLY, extra={"params": {"units": "lin"}})
    s = _Session(_Resp(payload=payload))
    f = get_fetcher("fred", api_key=SECRET, http=_http(s))
    df = f.fetch(_req(spec, "2024-01-01"))
    _check_canonical(df, 3, nan=1)
    p = s.calls[0]["params"]
    assert p["series_id"] == "UNRATE" and p["observation_start"] == "2024-01-01" and p["units"] == "lin"

    # avain puuttuu
    old = os.environ.pop("FRED_API_KEY", None)
    try:
        try:
            get_fetcher("fred")
            raise AssertionError("pitäisi nostaa FetcherError")
        except FetcherError:
            pass
    finally:
        if old is not None:
            os.environ["FRED_API_KEY"] = old

    # HTTP-virhe
    f = get_fetcher("fred", api_key=SECRET, http=_http(_Session(_Resp(400, text="Bad Request"))))
    try:
        f.fetch(_req(spec))
        raise AssertionError
    except FetchError as e:
        assert "400" in str(e)


# --- HttpClient -----------------------------------------------------------
def test_http_cache_retry_scrub():
    payload = {"observations": [{"date": "2024-01-01", "value": "1"}]}
    spec = SeriesSpec("x", "UNRATE", Frequency.MONTHLY)

    # välimuisti: toinen haku ei mene verkkoon, avain ei päädy levylle
    with tempfile.TemporaryDirectory() as tmp:
        s = _Session(_Resp(payload=payload))
        http = _http(s, cache_dir=tmp, ttl_seconds=3600)
        get_fetcher("fred", api_key=SECRET, http=http).fetch(_req(spec))
        get_fetcher("fred", api_key=SECRET, http=http).fetch(_req(spec))
        assert len(s.calls) == 1
        files = list(Path(tmp).glob("*.txt"))
        assert len(files) == 1 and SECRET not in files[0].read_text() and SECRET not in files[0].name
        # eri API-avain -> sama välimuistiosuma (avain ei ole avaimessa)
        get_fetcher("fred", api_key="OTHER", http=http).fetch(_req(spec))
        assert len(s.calls) == 1

    # uudelleenyritys 429:llä
    s = _Session(_Resp(429, text="slow down", headers={"Retry-After": "0"}), _Resp(payload=payload))
    get_fetcher("fred", api_key=SECRET, http=_http(s, retries=2)).fetch(_req(spec))
    assert len(s.calls) == 2

    # verkkovirhe: avain poistetaan virheviestistä
    err = requests.ConnectionError(f"failed ... api_key={SECRET} ...")
    f = get_fetcher("fred", api_key=SECRET, http=_http(_Session(err), retries=1))
    try:
        f.fetch(_req(spec))
        raise AssertionError
    except FetchError as e:
        assert SECRET not in str(e) and "***" in str(e)

    # kutsuväli: kaksi oikeaa kutsua -> sleep kutsuttu
    slept: list[float] = []
    t = iter([0.0, 0.5, 0.5])  # 1. kutsu: last=0.0; 2. kutsu: odotus 3.0-0.5, sitten last=0.5
    http = HttpClient(session=_Session(_Resp(payload=payload)), min_interval=3.0,
                      sleep=slept.append, clock=lambda: next(t))
    http.get("http://x/a")
    http.get("http://x/b")
    assert slept and abs(slept[0] - 2.5) < 1e-9


# --- OECD -----------------------------------------------------------------
def test_oecd():
    csv = ("STRUCTURE,STRUCTURE_ID,ACTION,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
           "dataflow,X,I,FIN,2024-01,7.1\ndataflow,X,I,FIN,2024-02,7.3\ndataflow,X,I,FIN,2024-03,\n")
    spec = SeriesSpec("FI.une.m", "OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0", Frequency.MONTHLY,
                      extra={"key": "FIN.UNE_LF_M.._Z.Y._T.Y_GE15..M"})
    s = _Session(_Resp(text=csv))
    df = get_fetcher("oecd", http=_http(s)).fetch(_req(spec, "2024-01-01"))
    _check_canonical(df, 3, nan=1)
    c = s.calls[0]
    assert c["headers"]["Accept"].startswith("application/vnd.sdmx.data+csv")
    assert c["params"]["startPeriod"] == "2024-01" and c["url"].endswith("/data/" + spec.source_code + "/" + spec.extra["key"])

    dup = csv + "dataflow,X,I,SWE,2024-01,6.0\n"
    try:
        get_fetcher("oecd", http=_http(_Session(_Resp(text=dup)))).fetch(_req(spec))
        raise AssertionError
    except SchemaError:
        pass


# --- Tilastokeskus --------------------------------------------------------
def _px_payload():
    return {
        "version": "2.0", "class": "dataset", "id": ["Tiedot", "Kuukausi"], "size": [1, 3],
        "role": {"time": ["Kuukausi"]},
        "dimension": {
            "Tiedot": {"category": {"index": {"tyottomyysaste": 0}}},
            "Kuukausi": {"category": {"index": {"2024M01": 0, "2024M02": 1, "2024M03": 2}}},
        },
        "value": [7.1, 7.3, None],
    }


def test_statfin():
    spec = SeriesSpec("FI.une.m", "tyonv/12tg.px", Frequency.MONTHLY,
                      extra={"query": {"Tiedot": ["tyottomyysaste"]}, "time_code": "Kuukausi"})
    s = _Session(_Resp(payload=_px_payload()))
    f = get_fetcher("tilastokeskus", http=_http(s))  # alias
    assert f.source_name == "statfin"
    df = f.fetch(_req(spec))
    _check_canonical(df, 3, nan=1)
    c = s.calls[0]
    assert c["method"] == "POST" and c["json"]["response"]["format"] == "json-stat2"
    assert {"code": "Kuukausi", "selection": {"filter": "all", "values": ["*"]}} in c["json"]["query"]

    f = get_fetcher("statfin", http=_http(_Session(_Resp(403, text="too many values"))))
    try:
        f.fetch(_req(spec))
        raise AssertionError
    except FetchError as e:
        assert "8.6.2026" in str(e)

    f = get_fetcher("statfin", http=_http(_Session(_Resp(payload={"title": "t", "variables": []}))))
    assert f.describe_table("tyonv/12tg.px")["title"] == "t"


# --- IMF ------------------------------------------------------------------
class _Client:
    def __init__(self):
        self.calls = []

    def data(self, flow, key=None, params=None):
        self.calls.append((flow, key, params))
        return "viesti"


def _imf_series(countries=("FIN",)):
    rows, vals = [], []
    for c in countries:
        for t, v in (("2024-M01", 1.0), ("2024-M02", 2.0), ("2024-M03", None)):
            rows.append((c, "CPI", "M", t))
            vals.append(v)
    idx = pd.MultiIndex.from_tuples(rows, names=["COUNTRY", "INDICATOR", "FREQUENCY", "TIME_PERIOD"])
    return pd.Series(vals, index=idx, dtype="float64")


def test_imf():
    spec = SeriesSpec("FI.cpi.m", "CPI", Frequency.MONTHLY, extra={"key": "FIN.CPI.M"})
    client = _Client()
    f = get_fetcher("imf", client=client, to_pandas=lambda msg: _imf_series())
    df = f.fetch(_req(spec, "2024-01-01"))
    _check_canonical(df, 3, nan=1)
    assert client.calls[0] == ("CPI", "FIN.CPI.M", {"startPeriod": "2024-01"})

    f = get_fetcher("imf", client=_Client(), to_pandas=lambda msg: _imf_series(("FIN", "SWE")))
    try:
        f.fetch(_req(spec))
        raise AssertionError
    except SchemaError:
        pass


def main() -> None:
    for t in (test_fred, test_http_cache_retry_scrub, test_oecd, test_statfin, test_imf):
        t()
        print("OK", t.__name__)


if __name__ == "__main__":
    main()
