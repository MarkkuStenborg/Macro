# ============================================================================
# File: macro_dashboard/latest_loader.py
# Purpose: Load latest macro indicator values from store/latest.json
# ============================================================================

import json
from pathlib import Path


LATEST_FILE = Path("store/latest.json")


def load_latest():

    with open(
        LATEST_FILE,
        encoding="utf-8"
    ) as f:

        return json.load(f)


if __name__ == "__main__":

    data = load_latest()

    print(
        f"Loaded {len(data)} indicators"
    )