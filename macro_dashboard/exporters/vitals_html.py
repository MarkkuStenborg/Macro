# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\exporters\vitals_html.py
"""Avainindikaattoriikkuna HTML:ksi (sivun alkuun).

Yksi kehys, jossa solut hiusviivoin erotettuna: alue ja nimi, tuorein arvo,
ajankohta ja muutos edelliseen havaintoon. Muutos on neutraali, paitsi
markkinahinnoilla (``Vital.color_change``) vihreä/punainen. Sparkline on
valinnainen (``sparklines=True``). Fontti Verdana. Tyylit ovat omassa
<style>-lohkossaan, joten osio ei riipu Tailwindista.
"""

from __future__ import annotations

import html
from typing import Sequence

import pandas as pd

from data_fetchers import Frequency
from vitals import VitalResult

__all__ = ["render_vitals", "format_number", "format_date"]

COLUMNS = 4  # sarakkeita työpöytänäkymässä (tyhjät solut täydentävät viimeisen rivin)
_SOURCE_LABEL = {
    "eurostat": "Eurostat",
    "fred": "FRED",
    "bundesbank": "Bundesbank",
    "suomenpankki": "Suomen Pankki",
}
_MINUS = "\u2212"
_NBSP = "\u00a0"

_CSS = """
.vt-root{font-family:Verdana,Geneva,'DejaVu Sans',sans-serif;color:#333}
.vt-root h2{font-size:1.15rem;font-weight:700;color:#0A2A5E;margin:0 0 .6rem;padding-bottom:.4rem;border-bottom:2px solid #0A2A5E}
.vt-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:#dfe3e8;
  border:1px solid #dfe3e8;border-radius:.6rem;overflow:hidden}
.vt-cell{background:#fff;padding:.8rem 1rem .7rem;display:flex;flex-direction:column;gap:.15rem;min-width:0}
.vt-label{font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;color:#6b7280;line-height:1rem}
.vt-reg{color:#0A2A5E;font-weight:700}
.vt-value{font-size:1.5rem;font-weight:700;color:#0A2A5E;line-height:2rem}
.vt-unit{font-size:.72rem;font-weight:400;color:#6b7280;margin-left:.2rem}
.vt-meta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:.1rem .5rem;font-size:.7rem;color:#6b7280}
.vt-delta{white-space:nowrap;color:#555}
.vt-up{color:#2e7d32;font-weight:700}
.vt-down{color:#c62828;font-weight:700}
.vt-na .vt-value{color:#b0b6bd}
.vt-spark{display:block;width:100%;height:26px;margin-top:.3rem}
.vt-foot{font-size:.68rem;font-style:italic;color:#7F8790;margin:.5rem .1rem 0}
@media (max-width:900px){.vt-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:480px){.vt-cell{padding:.6rem .65rem .5rem}.vt-value{font-size:1.25rem}
  .vt-label{min-height:2rem}}
"""


def format_number(x: float, decimals: int = 1, signed: bool = False) -> str:
    """Suomalainen luvunmuotoilu: desimaalipilkku, ohut tuhaterotin."""
    rounded = round(x, decimals)
    if signed:
        sign = "+" if rounded > 0 else (_MINUS if rounded < 0 else "\u00b1")
    else:
        sign = _MINUS if rounded < 0 else ""
    body = f"{abs(rounded):,.{decimals}f}"
    return sign + body.replace(",", _NBSP).replace(".", ",")


def format_date(d: pd.Timestamp, freq: Frequency) -> str:
    if freq is Frequency.MONTHLY:
        return f"{d.month}/{d.year}"
    if freq is Frequency.QUARTERLY:
        return f"{d.year} Q{(d.month - 1) // 3 + 1}"
    if freq is Frequency.ANNUAL:
        return str(d.year)
    return f"{d.day}.{d.month}.{d.year}"


def _sparkline(values: Sequence[float]) -> str:
    if len(values) < 2:
        return ""
    w, h, pad = 120.0, 26.0, 3.0
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    n = len(values) - 1
    pts = [
        (pad + (w - 2 * pad) * i / n, h - pad - (h - 2 * pad) * (v - lo) / span)
        for i, v in enumerate(values)
    ]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    lx, ly = pts[-1]
    return (
        f'<svg class="vt-spark" viewBox="0 0 {w:.0f} {h:.0f}" preserveAspectRatio="none" aria-hidden="true">'
        f'<polyline points="{poly}" fill="none" stroke="#0A2A5E" stroke-width="1.5" '
        f'vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2" fill="#0A2A5E"/></svg>'
    )


def _delta(r: VitalResult) -> str:
    v = r.vital
    if r.change is None:
        return ""
    unit = "%" if v.change == "pct" else "%-yks."
    rounded = round(r.change, v.change_decimals)
    arrow = "\u25b2" if rounded > 0 else ("\u25bc" if rounded < 0 else "\u25cf")
    cls = "vt-delta"
    if v.color_change and rounded != 0:
        cls += " vt-up" if rounded > 0 else " vt-down"
    text = f"{arrow} {format_number(r.change, v.change_decimals, signed=True)}{_NBSP}{unit}"
    return f'<span class="{cls}">{text}</span>'


def _cell(r: VitalResult, sparklines: bool) -> str:
    v = r.vital
    head = (
        f'<div class="vt-label"><span class="vt-reg">{html.escape(v.region)}</span>'
        f" \u00b7 {html.escape(v.display_label)}</div>"
    )
    if not r.ok:
        tip = html.escape(f"{v.label}: {r.error or 'ei havaintoja'}", quote=True)
        return (
            f'<div class="vt-cell vt-na" title="{tip}">{head}'
            f'<div class="vt-value">\u2013</div>'
            f'<div class="vt-meta"><span>Ei saatavilla</span></div></div>'
        )
    unit = f'<span class="vt-unit">{html.escape(v.unit)}</span>' if v.unit else ""
    tip_parts = [v.label]
    if r.previous is not None:
        tip_parts.append(f"edellinen: {format_number(r.previous, v.decimals)}")
    if r.geo_used:
        tip_parts.append(f"alue: {r.geo_used}")
    tip = html.escape(" \u00b7 ".join(tip_parts), quote=True)
    spark = _sparkline(r.spark) if sparklines else ""
    return (
        f'<div class="vt-cell" title="{tip}">{head}'
        f'<div class="vt-value">{format_number(r.value, v.decimals)}{unit}</div>'
        f'<div class="vt-meta"><span>{format_date(r.date, v.frequency)}</span>{_delta(r)}</div>'
        f"{spark}</div>"
    )


def render_vitals(
    results: Sequence[VitalResult],
    title: str = "Keskeiset indikaattorit",
    sparklines: bool = False,
) -> str:
    """Palauta koko osio (``<style>`` + ``<section>``) HTML-merkkijonona."""
    cells = [_cell(r, sparklines) for r in results]
    cells += ['<div class="vt-cell vt-empty"></div>'] * ((-len(cells)) % COLUMNS)
    used = [r.vital.source for r in results if r.ok] or [r.vital.source for r in results]
    sources = ", ".join(sorted({_SOURCE_LABEL.get(s, s) for s in used}))
    foot = (
        f"Lähteet: {html.escape(sources)}. Muutos edelliseen havaintoon; "
        "ajankohdat vaihtelevat julkaisutahdin mukaan."
    )
    return (
        f"<style>{_CSS}</style>"
        f'<section class="vt-root"><h2>{html.escape(title)}</h2>'
        f'<div class="vt-grid">{"".join(cells)}</div>'
        f'<p class="vt-foot">{foot}</p></section>'
    )
