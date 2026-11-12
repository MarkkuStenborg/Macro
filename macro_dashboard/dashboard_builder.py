# ============================================================================
# File: macro_dashboard/dashboard_builder.py
# ============================================================================

from pathlib import Path

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def build_dashboard():

    html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Macro Dashboard</title>
</head>
<body>

<h1>Macro Dashboard</h1>

<h2>Finland</h2>
<p>GDP</p>
<p>Inflation</p>
<p>Unemployment</p>

<h2>Euro Area</h2>
<p>GDP</p>
<p>Inflation</p>

<h2>USA</h2>
<p>GDP</p>
<p>Inflation</p>

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
