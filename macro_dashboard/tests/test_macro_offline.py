# ============================================================================
# File: macro_dashboard/tests/test_macro_offline.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\tests\test_macro_offline.py
"""Offline-testi makroseurannalle. Data on TEKAISTUA (satunnaiskulku), joten testi tarkistaa
vain luettelon latauksen, varaehdokkaat, muunnokset, virheiden eristyksen ja sivujen rakenteen.
Aja kansiosta macro_dashboard:  python -m tests.test_macro_offline
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import config
from data_fetchers import FetchError, Frequency
from macro.catalog import load_catalog
from macro.pages import build_site, collect_series
from macro.store import Store
from macro.transforms import apply_transform
from macro.update import update_catalog

TODAY = pd.Timestamp("2026-11-05")
_FREQ = {Frequency.MONTHLY: "MS", Frequency.QUARTERLY: "QS", Frequency.ANNUAL: "YS", Frequency.DAILY: "D"}
CALLS: list[tuple[str, str, str | None]] = []


def fake_fetch(source, specs, start=None, end=None, **kw):
    spec = specs[0]
    CALLS.append((source, spec.source_code, spec.geo))
    if spec.geo == "EA":  # euroalueen ensimmäinen geo-ehdokas ei kelpaa -> varakoodi EA21
        raise FetchError("HTTP 400 tuntematon geo")
    key = spec.extra.get("key", "")
    if spec.source_code in ("CPALTT01CNM657N",) or (spec.geo == "CHN" and "PRICES" in spec.source_code) \
            or (spec.geo in ("CHN", "GBR") and "PRVM" in key):
        raise FetchError("HTTP 400 sarjaa ei ole")  # Kiina: kokonaan puuttuva; UK: OECD-haku tyhjä -> FRED-varasarja
    rng = np.random.default_rng(abs(hash((spec.source_code, spec.geo))) % 2**32)
    last = TODAY - pd.DateOffset(months=40) if spec.source_code == "GBRPROINDMISMEI" else TODAY  # vanha -> varasarja
    idx = pd.date_range(start, last, freq=_FREQ[spec.frequency])
    base = 100.0
    vals = base + np.cumsum(rng.normal(0.1, 0.8, len(idx)))
    return pd.DataFrame({spec.series_id: vals}, index=pd.DatetimeIndex(idx, name="date"))


def test_transforms() -> None:
    idx = pd.date_range("2024-01-01", periods=30, freq="MS")
    s = pd.Series(np.arange(100.0, 130.0), index=idx)
    yoy = apply_transform(s, "yoy", Frequency.MONTHLY)
    assert abs(yoy.iloc[0] - (112 / 100 - 1) * 100) < 1e-9 and len(yoy) == 18
    gap = s.drop(s.index[5])  # puuttuva kuukausi ei saa siirtää viivettä
    assert abs(apply_transform(gap, "yoy", Frequency.MONTHLY).loc["2025-01-01"] - (112 / 100 - 1) * 100) < 1e-9
    assert abs(apply_transform(s, "pch", Frequency.MONTHLY).iloc[0] - 1.0) < 1e-9
    assert apply_transform(s, None, Frequency.MONTHLY).equals(s)


def main() -> None:
    test_transforms()
    cat = load_catalog(config.CATALOG_DIR)
    assert "labour" in cat.themes and {"unemp", "employment_yoy", "wages_yoy", "vacancy_rate"} <= set(cat.indicators)
    ea = next(s for s in cat.series if s.id == "EA.unemp")
    assert [c.geo for c in ea.cands] == ["EA", "EA21", "EA20"], "euroalueen geo-ehdokkaat järjestyksessä"
    bci = next(s for s in cat.series if s.id == "EA.bci")
    assert [(c.source, c.geo) for c in bci.cands[:2]] == [("oecd", "EA20"), ("oecd", "EA21")]
    assert bci.cands[-1].source == "fred", "FRED jää viimeiseksi varaksi"
    assert bci.cands[0].params["key"] == "EA20.M.BCICP.IX._Z.AA.IX._Z.H", "OECD-avaimen {geo}-malli täyttyy"
    assert next(s for s in cat.series if s.id == "FR.vacancy_rate").cands[0].params["indic_em"] == "JVR"

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "store")
        rep = update_catalog(cat, store, today=TODAY, fetch=fake_fetch)
        assert rep.ok, "jotain pitää onnistua"
        assert "CN.cpi_mom" in rep.failed, "puuttuva sarja raportoidaan eikä kaada muita"
        assert rep.ok["EA.unemp"]["geo"] == "EA21", "varakoodi EA21 käyttöön, kun EA ei kelpaa"
        assert not rep.ok["UK.ip_yoy"]["stale"] and rep.ok["UK.ip_yoy"]["code"] == "PRMNTO01GBM661S", \
            "vanha ensisijainen sarja korvautuu tuoreella varasarjalla"
        # sama lähdehaku jaetaan: y/y ja m/m eivät hae US:n INDPRO:a kahdesti
        assert sum(1 for c in CALLS if c[1] == "INDPRO") == 1
        n1 = len(CALLS)
        rep2 = update_catalog(cat, store, today=TODAY, fetch=fake_fetch)
        assert rep2.fetched == 0 or len(CALLS) - n1 < n1 * 0.2, "toinen ajo käyttää varastoa"

        data = collect_series(cat, store)
        assert data["US.cpi_yoy"].s.index[-1] <= TODAY and not data["FI.unemp"].s.empty

        out = Path(tmp) / "site"
        files = build_site(cat, store, out, write_plotly_js=False)
        names = {p.name for p in files}
        assert {"index.html", "region_FI.html", "theme_labour.html", "region_US.html"} <= names, names
        idx_html = (out / "index.html").read_text(encoding="utf-8")
        assert "Työttömyysaste" in idx_html and "Puuttuvat sarjat" in idx_html and "CN.cpi_mom" in idx_html
        fi = (out / "region_FI.html").read_text(encoding="utf-8")
        assert "Työmarkkinat" in fi and fi.count('class="chart"') >= 10
        assert "Kopioi kuva" in fi and "IntersectionObserver" in fi
        th = (out / "theme_labour.html").read_text(encoding="utf-8")
        assert th.count('class="chart"') == 5
        print(f"OK: {len(rep.ok)} sarjaa haettu, {len(rep.failed)} puuttuu, {len(files)} tiedostoa")
        print("Esimerkki puuttuvista:", ", ".join(sorted(rep.failed)[:5]))


if __name__ == "__main__":
    main()
