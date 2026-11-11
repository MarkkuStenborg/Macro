# ============================================================================
# File: macro_dashboard/config.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\config.py
"""Globaalit asetukset. API-avaimet luetaan ympäristömuuttujista, ei koodista."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / ".cache"  # HTTP-vastausten välimuisti (ks. data_fetchers.HttpClient)
DATA_DIR = BASE_DIR / "data"  # käsin ladatut lähdetiedostot
# Suomen Pankin viitelainojen tuotot: raportin Export -> CSV tähän tiedostoon
BOF_CSV = DATA_DIR / "viitelainojen_korot.csv"

FRED_API_KEY: str | None = os.environ.get("FRED_API_KEY")

STORE_DIR = BASE_DIR / "store"  # haettu sarjadata (macro.store)
CATALOG_DIR = BASE_DIR / "catalog"  # sarjaluettelot (*.yaml)
SITE_DIR = OUTPUT_DIR / "makro"  # makroseurannan sivut
