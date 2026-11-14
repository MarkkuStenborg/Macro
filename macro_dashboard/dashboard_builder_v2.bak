# ============================================================================
# File: macro_dashboard/dashboard_builder_v2.py
# ============================================================================

from pathlib import Path

from dashboard_cards import CARDS


OUTPUT_DIR = Path("output")

OUTPUT_DIR.mkdir(exist_ok=True)


def build_dashboard():

    cards_html = []

    rows = build_dashboard_dataset()

for card in rows:

        cards_html.append(f"""
<div class="card">

    <div class="country">
        {card["country"]}
    </div>

    <div class="title">
        {card["title"]}
    </div>

    <div class="value">
        {card["value"]} {card["unit"]}
    </div>

    <div class="date">
        {card["date"]}
    </div>

    <div class="change">
        {card["change"]}
    </div>

</div>
""")

<!DOCTYPE html>
<html>

<head>
<meta charset="utf-8">

<title>Talouden indikaattorit</title>

<style>

body {
    font-family: Segoe UI, Arial, sans-serif;
    background: #f5f5f5;
    margin: 40px;
}

.grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}

.card {
    background: white;
    border: 1px solid #d7dbe2;
    border-radius: 10px;
    padding: 20px;
}

</style>

</head>

<body>

<h1>Talouden indikaattorit</h1>

<div class="grid">

__CARDS__

</div>

</body>
</html>
"""

html = html.replace(
    "__CARDS__",
    "".join(cards_html)
)

outfile.write_text(
    html,
    encoding="utf-8"
)

html = html.replace(
    "__CARDS__",
    "".join(cards_html)
)


</style>
</head>

<body>

<h1>Talouden indikaattorit</h1>

<div class="grid">

{''.join(cards_html)}

</div>

</body>
</html>
"""

    outfile = OUTPUT_DIR / "dashboard.html"

    outfile.write_text(
        html,
        encoding="utf-8"
    )

    print(outfile)


if __name__ == "__main__":
    build_dashboard()