# ============================================================================
# File: macro_dashboard/probe.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\probe.py
"""Tutki, mitä dimensioita ja arvoja Eurostatin ja OECD:n aineistoissa on (sarjakoodien korjaamiseen).

    python probe.py --all                       # ajaa vakiotutkimukset, kirjoittaa probe_output.txt
    python probe.py eurostat jvs_q_nace2 FI     # yksi Eurostat-aineisto, yksi maa
    python probe.py dbn-series STATJP/CPIm "all items"   # DBnomics: aineiston sarjat
    python probe.py dbn-datasets NBS                      # DBnomics: palveluntarjoajan aineistot
    python probe.py ecb STS "M..Y.ORDT.NS0062.3.000"   # EKP:n SDMX-data
    python probe.py oecd "OECD.SDD.STES,DSD_STES@DF_CLI" "JPN.M....."   # OECD: dataflow + dimensioavain

Kerro tulos (probe_output.txt) Claudelle; sen perusteella luettelon filtterit korjataan.
"""

from __future__ import annotations

import io
import sys
from typing import Any

import pandas as pd
import requests

EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
OECD = "https://sdmx.oecd.org/public/rest/data"
ECB = "https://data-api.ecb.europa.eu/service/data"
MAX_CATS = 40

# (tyyppi, aineisto, maa / dimensioavain, selite)
STANDARD = [
    # Kiinan NBS: kuukausi- ja neljännesvuosiaineistot (KPI, teollisuus, BKT)
    ("dbn-datasets", "NBS", "M_", "NBS: kuukausiaineistot"),
    ("dbn-datasets", "NBS", "Q_", "NBS: neljännesvuosiaineistot"),
    # Kiinan teollisuustuotanto muista DBnomics-lähteistä
    ("dbn-series", "IMF/PGI", "China industrial production", "IMF Principal Global Indicators: Kiinan teollisuus"),
    ("dbn-series", "UNIDO/MONTHLY_IIP", "China", "UNIDO: Kiinan teollisuustuotanto"),
]


def summarize_jsonstat(p: dict[str, Any]) -> str:
    out = []
    ids, sizes = p["id"], p["size"]
    out.append(f"dimensiot: {', '.join(f'{i}({n})' for i, n in zip(ids, sizes))}")
    for dim in ids:
        cat = p["dimension"][dim]["category"]
        labels = cat.get("label", {})
        codes = list(cat["index"]) if isinstance(cat["index"], dict) else list(cat["index"])
        shown = codes[:MAX_CATS]
        txt = "; ".join(f"{c}={labels.get(c, '')[:38]}" for c in shown)
        more = f" ... (+{len(codes) - len(shown)})" if len(codes) > len(shown) else ""
        out.append(f"  {dim}: {txt}{more}")
        if more:  # laajoissa luokituksissa näytä myös erikoisryhmät (koodit, jotka eivät ala CP:llä)
            special = [c for c in codes[MAX_CATS:] if not c.startswith("CP")][:80]
            if special:
                out.append("    erikoisryhmät: " + "; ".join(f"{c}={labels.get(c, '')[:44]}" for c in special))
    n = sum(1 for v in (p.get("value") or {}).values() if v is not None) if isinstance(p.get("value"), dict) \
        else sum(1 for v in (p.get("value") or []) if v is not None)
    out.append(f"  (havaintoja vastauksessa: {n})")
    return "\n".join(out)


def summarize_csv(text: str) -> str:
    df = pd.read_csv(io.StringIO(text), dtype=str)
    skip = {"OBS_VALUE", "TIME_PERIOD", "OBS_STATUS"}
    out = [f"rivejä {len(df)}; sarakkeet: {', '.join(df.columns)}"]
    for c in df.columns:
        if c in skip or c.startswith(("DATAFLOW", "STRUCTURE")):
            continue
        vals = sorted(df[c].dropna().unique())
        shown = vals[:MAX_CATS]
        out.append(f"  {c}: {'; '.join(shown)}" + (f" ... (+{len(vals) - len(shown)})" if len(vals) > len(shown) else ""))
    if "TIME_PERIOD" in df:
        out.append(f"  viimeisin TIME_PERIOD: {df['TIME_PERIOD'].max()}")
        keys = [c for c in ("REF_AREA", "MEASURE") if c in df.columns]
        if keys:
            g = df.groupby(keys)["TIME_PERIOD"].max()
            out.append("  tuoreus (" + "/".join(keys) + " -> viim. jakso):")
            out += [f"    {'/'.join(k) if isinstance(k, tuple) else k}: {v}" for k, v in list(g.items())[:80]]
    return "\n".join(out)


def probe_eurostat(dataset: str, geo: str) -> str:
    r = requests.get(f"{EUROSTAT}/{dataset}", params={"format": "JSON", "lang": "EN", "geo": geo,
                                                      "lastTimePeriod": 1}, timeout=60)
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:300]}"
    return summarize_jsonstat(r.json())


def probe_oecd(flow: str, key: str) -> str:
    r = requests.get(f"{OECD}/{flow}/{key}", params={"lastNObservations": 1, "format": "csvfile"},
                     headers={"Accept": "application/vnd.sdmx.data+csv; charset=utf-8"}, timeout=90)
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:300]}"
    return summarize_csv(r.text)


def probe_ecb(flow: str, key: str) -> str:
    r = requests.get(f"{ECB}/{flow}/{key}", params={"lastNObservations": 1, "format": "csvdata"}, timeout=90)
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:300]}"
    return summarize_csv(r.text)


def summarize_dbnomics(payload: dict[str, Any]) -> str:
    res = payload.get("results", {})
    docs = res.get("docs", [])
    out = [f"osumia {res.get('num_found', len(docs))}; 12 ensimmäistä (palveluntarjoaja/aineisto: nimi, sarjoja):"]
    for d in docs[:12]:
        out.append(f"  {d.get('provider_code')}/{d.get('code')}: {str(d.get('name'))[:70]} ({d.get('nb_series')})")
    return "\n".join(out)


def probe_dbnomics(query: str, _unused: str = "") -> str:
    r = requests.get("https://api.db.nomics.world/v22/search", params={"q": query, "limit": 12}, timeout=60)
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:300]}"
    return summarize_dbnomics(r.json())


KEYWORDS = ("industr", "value added", "consumer price", "gdp", "gross domestic", "retail", "unemploy",
            "pmi", "purchasing", "producer price", "fixed asset", "export", "import")


def probe_dbn_series(dataset: str, query: str = "") -> str:
    """Luettele aineiston sarjat: koodi, nimi, viimeisin jakso ja arvo."""
    r = requests.get(f"https://api.db.nomics.world/v22/series/{dataset}",
                     params={"q": query, "limit": 20, "observations": 1, "format": "json"}, timeout=90)
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:300]}"
    res = r.json().get("series", {})
    docs = res.get("docs", [])
    out = [f"sarjoja yhteensä {res.get('num_found', len(docs))}; näytetään {len(docs)}:"]
    for d in docs:
        per, val = d.get("period") or [], d.get("value") or []
        last = f"{per[-1]}={val[-1]}" if per and val else "ei havaintoja"
        out.append(f"  {dataset}/{d.get('series_code')}  [{last}]  {str(d.get('series_name'))[:90]}")
    return "\n".join(out)


def probe_dbn_datasets(provider: str, prefix: str = "") -> str:
    """Luettele palveluntarjoajan aineistot. prefix (esim. M_ tai Q_) rajaa koodin alun mukaan."""
    docs: list[dict[str, Any]] = []
    for offset in range(0, 3000, 500):  # DBnomics palauttaa max 500 kerrallaan
        r = requests.get(f"https://api.db.nomics.world/v22/datasets/{provider}",
                         params={"limit": 500, "offset": offset}, timeout=90)
        if r.status_code != 200:
            return f"HTTP {r.status_code}: {r.text[:300]}"
        page = (r.json().get("datasets") or {}).get("docs", [])
        docs += page
        if len(page) < 500:
            break
    if prefix:
        hit = [d for d in docs if str(d.get("code", "")).startswith(prefix)]
    else:
        hit = [d for d in docs if any(k in str(d.get("name", "")).lower() for k in KEYWORDS)]
    out = [f"aineistoja {len(docs)}, valittu {len(hit)}:"]
    out += [f"  {provider}/{d.get('code')}: {str(d.get('name'))[:90]}" for d in hit[:300]]
    return "\n".join(out)


def run(kind: str, a: str, b: str) -> str:
    try:
        return {"eurostat": probe_eurostat, "oecd": probe_oecd, "ecb": probe_ecb, "dbnomics": probe_dbnomics,
                "dbn-series": probe_dbn_series, "dbn-datasets": probe_dbn_datasets}[kind](a, b)
    except Exception as exc:  # tutkimus ei saa kaatua yhteen virheeseen
        return f"VIRHE {type(exc).__name__}: {exc}"


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--all":
        lines: list[str] = []
        for kind, a, b, note in STANDARD:
            head = f"=== {kind} {a} {b}  ({note})"
            print(head, flush=True)
            res = run(kind, a, b)
            print(res, flush=True)
            lines += [head, res, ""]
        with open("probe_output.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print("\nTulos tallennettu: probe_output.txt")
        return 0
    if argv and argv[0] == "dbnomics" and len(argv) == 2:
        print(run("dbnomics", argv[1], ""))
        return 0
    if argv and argv[0] in ("dbn-series", "dbn-datasets") and len(argv) in (2, 3):
        print(run(argv[0], argv[1], argv[2] if len(argv) == 3 else ""))
        return 0
    if len(argv) == 3 and argv[0] in ("eurostat", "oecd", "ecb"):
        print(run(*argv))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
