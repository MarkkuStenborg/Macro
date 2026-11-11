# ============================================================================
# File: macro_dashboard/build_site.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\build_site.py
"""Makroseuranta: hae sarjat luettelosta varastoon ja rakenna sivut.

Aja kansiosta macro_dashboard:

    python build_site.py                 # päivitä (välimuisti 12 h) + rakenna sivut
    python build_site.py --check         # pakota uusi haku, tulosta raportti, älä rakenna sivuja
    python build_site.py --build-only    # rakenna sivut varastosta ilman verkkohakuja
    python build_site.py --themes labour prices   # päivitä vain nämä teemat
    python build_site.py --force         # ohita välimuisti

Sarjat lisätään tai korjataan vain tiedostoissa catalog/*.yaml. FRED vaatii FRED_API_KEY:n
(ks. set_fred_key.py). Tulos: output/makro/index.html (+ aluesivut ja teemasivut).
"""

from __future__ import annotations

import argparse
import sys

import config
from data_fetchers import HttpClient
from macro.catalog import load_catalog
from macro.pages import build_site
from macro.store import Store
from macro.update import update_catalog


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="pakota haku ja tulosta OK/EI-raportti; ei sivuja")
    ap.add_argument("--build-only", action="store_true", help="ei hakuja, vain sivut varastosta")
    ap.add_argument("--force", action="store_true", help="ohita varaston tuoreus")
    ap.add_argument("--themes", nargs="+", metavar="TEEMA", help="päivitä vain nämä teemat")
    ap.add_argument("--years", type=int, default=25, help="haettavan historian pituus vuosina")
    ap.add_argument("--out", default=str(config.SITE_DIR), help="sivujen kohdekansio")
    args = ap.parse_args(argv)

    catalog = load_catalog(config.CATALOG_DIR)
    store = Store(config.STORE_DIR)
    print(f"Luettelo: {len(catalog.regions)} aluetta, {len(catalog.indicators)} indikaattoria, "
          f"{len(catalog.series)} sarjaa")

    if not args.build_only:
        if args.themes:
            unknown = set(args.themes) - set(catalog.themes)
            if unknown:
                print(f"Tuntemattomat teemat: {sorted(unknown)}; sallitut: {sorted(catalog.themes)}")
                return 2

        def http() -> HttpClient:
            return HttpClient(cache_dir=config.CACHE_DIR, ttl_seconds=3600)

        report = update_catalog(
            catalog, store,
            history_years=args.years,
            force=args.force or args.check,
            only_themes=set(args.themes) if args.themes else None,
            fetch_kwargs={"fred": {"http": http()}, "worldbank": {"http": http()}},
            log=(lambda m: print("  " + m)) if args.check else (lambda m: None),
        )
        print(f"\nHaettu verkosta: {report.fetched}, välimuistista: {report.cached}")
        print(f"Sarjoja: {len(report.ok)} OK, {len(report.failed)} puuttuu")
        if args.check or report.failed:
            print()
            for line in report.lines():
                if args.check or line.startswith("EI"):
                    print(line)
        if args.check:
            return 0 if not report.failed else 1

    written = build_site(catalog, store, args.out)
    print(f"\nSivut: {args.out}  ({len([p for p in written if p.suffix == '.html'])} html-sivua)")
    print(f"Avaa: {args.out}\\index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
