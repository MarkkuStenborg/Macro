# ============================================================================
# File: macro_dashboard/dashboard_data.py
# Purpose: Prepare dashboard rows for rendering
# ============================================================================

# yhdistää dashboard_cards.py + store/latest.json

from dashboard_cards import CARDS


def build_dashboard_dataset():

    rows = []

    for card in CARDS:

        rows.append({

            "country": card.get("country", ""),

            "title": card.get("title", ""),

            "value": card.get("value", ""),

            "unit": card.get("unit", ""),

            "date": card.get("date", ""),

            "change": card.get("change", "")

        })

    return rows


if __name__ == "__main__":

    rows = build_dashboard_dataset()

    print()
    print(f"Loaded {len(rows)} dashboard rows")
    print()

    for row in rows:

        print(
            f"{row['country']} | "
            f"{row['title']} | "
            f"{row['value']} {row['unit']}"
        )