# ============================================================================
# File: macro_dashboard/exporters/html_generator.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\exporters\html_generator.py
"""Plotly-kuvaajien upotus siistiin, responsiiviseen Tailwind-pohjaan.

Kuvion otsikko, alaotsikko ja lähde ovat itse Plotly-kuvion sisällä
(``apply_macrobond_style``), joten kuvan kopioiminen/vienti ottaa ne mukaan.
Sivun oma otsikko on vain navigointia ja jäsentelyä varten.

Tailwind ja Plotly ladataan CDN:stä, joten sivu tarvitsee verkkoyhteyden.
Tailwindin CDN-skripti on tarkoitettu kehitys- ja pienkäyttöön; julkaistavaan
sivustoon kannattaa myöhemmin vaihtaa ennalta käännetty CSS.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Sequence

import plotly.graph_objects as go

__all__ = ["build_html", "save_html"]

_FONT = "Verdana, Geneva, 'DejaVu Sans', sans-serif"

_PLOTLY_CONFIG = {
    "responsive": True,
    "displaylogo": False,
    "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "kuvio"},
}


# "Kopioi kuva": renderöi kuvion PNG:ksi (otsikko, selitteet ja lähde mukana,
# koska ne ovat kuvion sisällä) ja kopioi leikepöydälle. Vaatii selaimen
# Clipboard API:n kuvatuen (Chrome/Edge/Safari, Firefox 127+).
_COPY_SCRIPT = """
document.querySelectorAll('[data-copy-chart]').forEach(function (btn) {
  var label = btn.textContent;
  btn.addEventListener('click', async function () {
    var gd = btn.closest('section').querySelector('.plotly-graph-div');
    try {
      var url = await Plotly.toImage(gd, {format: 'png', scale: 2});
      var blob = await (await fetch(url)).blob();
      await navigator.clipboard.write([new ClipboardItem({'image/png': blob})]);
      btn.textContent = 'Kopioitu';
    } catch (e) {
      console.error(e);
      btn.textContent = 'Kopiointi ei onnistunut \\u2013 k\\u00e4yt\\u00e4 kamerakuvaketta';
    }
    setTimeout(function () { btn.textContent = label; }, 3000);
  });
});
"""


def build_html(
    figures: go.Figure | Sequence[go.Figure],
    *,
    page_title: str,
    heading: str | None = None,
    description: str | None = None,
    chart_height_px: int = 520,
    updated: datetime | None = None,
    lang: str = "fi",
    top_html: str = "",
) -> str:
    """Palauta kokonainen HTML-sivu merkkijonona.

    ``figures`` voi olla yksittäinen kuvio tai sarja kuvioita; jokainen
    sijoitetaan omaan korttiinsa allekkain. ``top_html`` (esim. avainindikaattorilaatat,
    ``exporters.vitals_html.render_vitals``) sijoitetaan kuvioiden yläpuolelle.
    """
    figs = [figures] if isinstance(figures, go.Figure) else list(figures)
    if not figs:
        raise ValueError("Vähintään yksi kuvio tarvitaan")

    cards = []
    for i, fig in enumerate(figs):
        fig.update_layout(autosize=True)
        fragment = fig.to_html(
            full_html=False,
            include_plotlyjs="cdn" if i == 0 else False,  # kirjasto vain kerran
            config=_PLOTLY_CONFIG,
            default_width="100%",
            default_height=f"{chart_height_px}px",
        )
        cards.append(
            '<section class="bg-white rounded-lg shadow-sm ring-1 ring-slate-200 '
            'p-3 sm:p-5 overflow-hidden">'
            '<div class="mb-2 flex justify-end">'
            '<button type="button" data-copy-chart '
            'class="rounded border border-slate-300 bg-white px-2.5 py-1 text-xs '
            'text-slate-600 hover:bg-slate-100">Kopioi kuva</button></div>'
            f"{fragment}</section>"
        )

    stamp = (updated or datetime.now()).strftime("%d.%m.%Y %H:%M")
    h = html.escape(heading or page_title)
    desc_html = (
        f'<p class="mt-2 max-w-3xl text-sm text-slate-600">{html.escape(description)}</p>'
        if description
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="{html.escape(lang)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(page_title)}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>body {{ font-family: {_FONT}; }}</style>
</head>
<body class="bg-slate-50 text-slate-800 antialiased">
  <header class="border-b border-slate-200 bg-white">
    <div class="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <h1 class="text-xl font-bold text-[#0A2A5E] sm:text-2xl">{h}</h1>
      {desc_html}
    </div>
  </header>
  <main class="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6">
    {top_html}
    {"".join(cards)}
  </main>
  <footer class="mx-auto max-w-6xl px-4 pb-8 text-xs text-slate-500 sm:px-6">
    Päivitetty {stamp}
  </footer>
  <script>{_COPY_SCRIPT}</script>
</body>
</html>
"""


def save_html(path: str | Path, figures: go.Figure | Sequence[go.Figure], **kwargs) -> Path:
    """Kirjoita sivu tiedostoon (UTF-8) ja palauta polku."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_html(figures, **kwargs), encoding="utf-8")
    return path
