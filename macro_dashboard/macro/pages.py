# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\macro\pages.py
"""Makroseurannan sivut varastosta (``macro.store.Store``) ja luettelosta.

Tuottaa kansioon ``out_dir``:

* ``index.html``          : viimeisimmät arvot, indikaattori x alue, linkit sivuille
* ``region_<ID>.html``    : yhden alueen kaikki indikaattorit teemoittain (+ viitealueet harmaasti)
* ``theme_<id>.html``     : yhden teeman indikaattorit, kaikki alueet samassa kuviossa (maavertailu)
* ``plotly.min.js``       : Plotly paikallisena kopiona (sivut toimivat ilman CDN:ää)

Kuviot upotetaan JSON:ina ja piirretään vasta, kun ne vierivät näkyviin
(IntersectionObserver); sadat kuviot eivät siis kuormita selainta kerralla.
Kuvion otsikko, alaotsikko ja lähde ovat kuvion sisällä (Macrobond-tyyli), joten
"Kopioi kuva" -painike vie ne mukaan.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from data_fetchers import Frequency
from visualization.macrobond_theme import PALETTE, apply_macrobond_style
from .catalog import Catalog, Indicator, Region, SeriesDef
from .store import Store
from .transforms import apply_transform

__all__ = ["SeriesData", "collect_series", "build_site"]

_SOURCE_NAME = {"eurostat": "Eurostat", "fred": "FRED", "worldbank": "Maailmanpankki",
                "oecd": "OECD", "imf": "IMF", "bundesbank": "Bundesbank", "statfin": "Tilastokeskus"}
_FONT = "Verdana, Geneva, 'DejaVu Sans', sans-serif"
_CHART_H = 440
_PLOTLY_CONFIG = {"responsive": True, "displaylogo": False,
                  "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "kuvio"}}


@dataclass
class SeriesData:
    sdef: SeriesDef
    s: pd.Series  # muunnettu, ei tyhjä
    info: dict[str, Any]  # update.resolve-tulos (source, code, geo, last_obs, stale ...)

    @property
    def source_name(self) -> str:
        return _SOURCE_NAME.get(self.info["source"], self.info["source"])


def collect_series(catalog: Catalog, store: Store) -> dict[str, SeriesData]:
    """Lue ratkaistut sarjat varastosta ja tee niille luettelon määräämä muunnos."""
    resolved = store.load_resolved()
    out: dict[str, SeriesData] = {}
    for sd in catalog.series:
        info = resolved.get(sd.id)
        if not info:
            continue
        raw = store.load(info["raw_key"])
        if raw is None or raw.empty:
            continue
        try:
            s = apply_transform(raw, info.get("post"), Frequency(info["freq"]))
        except ValueError:
            continue
        if not s.empty:
            out[sd.id] = SeriesData(sd, s, info)
    return out


# --------------------------------------------------------------- muotoilu

def _fmt(v: float, decimals: int) -> str:
    t = f"{abs(v):,.{decimals}f}".replace(",", "\u00a0").replace(".", ",")
    return ("\u2212" + t) if v < 0 and float(t.replace("\u00a0", "").replace(",", ".")) != 0 else t


def _period_label(ts: pd.Timestamp, freq: str) -> str:
    if freq == "Q":
        return f"{ts.year} Q{(ts.month - 1) // 3 + 1}"
    if freq == "A":
        return str(ts.year)
    return f"{ts.month}/{ts.year}"


# ----------------------------------------------------------------- kuviot

def _figure(
    ind: Indicator, items: list[tuple[SeriesData, Region, bool]], *, title: str, as_bars: bool
) -> go.Figure:
    """``items``: (sarja, alue, korostettu). Korostettu = alueen oma sarja; muut viitteitä."""
    end = max(sd.s.index[-1] for sd, _, _ in items)
    start = end - pd.DateOffset(years=ind.years)
    fig = go.Figure()
    for sd, reg, main in items:
        s = sd.s[sd.s.index >= start]
        color = reg.color or PALETTE[len(fig.data) % len(PALETTE)]
        if as_bars:
            fig.add_trace(go.Bar(x=s.index, y=s.round(4), name=reg.name, marker=dict(color=color)))
        else:
            mode = "lines+markers" if ind.freq is Frequency.ANNUAL else "lines"
            line = dict(color=color, width=2.4 if main else 1.6, dash="solid" if main else "dot")
            fig.add_trace(go.Scatter(x=s.index, y=s.round(4), name=reg.name, mode=mode, line=line,
                                     marker=dict(size=5, color=color)))
    sources = sorted({sd.source_name for sd, _, _ in items})
    apply_macrobond_style(fig, title=title, subtitle=ind.unit, source=", ".join(sources), x_range=(start, end))
    fig.update_layout(autosize=True, height=None, width=None)
    return fig


def _card(idx: int, fig: go.Figure, ind: Indicator, items: list[tuple[SeriesData, Region, bool]]) -> str:
    payload = fig.to_json().replace("</", "<\\/")
    rows = "".join(
        f"<tr><td>{html.escape(reg.name)}</td><td>{html.escape(sd.info['source'])}:{html.escape(sd.info['code'])}"
        f"{(' ' + html.escape(sd.info['geo'])) if sd.info.get('geo') else ''}</td>"
        f"<td>{_period_label(sd.s.index[-1], sd.info['freq'])}</td>"
        f"<td>{'vanha' if sd.info.get('stale') else ''}</td></tr>"
        for sd, reg, _ in items
    )
    note = f'<p class="note">{html.escape(ind.note)}</p>' if ind.note else ""
    return (
        f'<section class="card"><div class="tools"><button type="button" data-copy>Kopioi kuva</button></div>'
        f'<div class="chart" data-fig="fig-{idx}" style="height:{_CHART_H}px"></div>'
        f'<script type="application/json" id="fig-{idx}">{payload}</script>{note}'
        f'<details><summary>Sarjat</summary><table class="series"><tr><th>Alue</th><th>Lähde</th>'
        f"<th>Viim. havainto</th><th></th></tr>{rows}</table></details></section>"
    )


_JS = """
var CFG = %s;
var io = new IntersectionObserver(function (entries) {
  entries.forEach(function (e) {
    if (!e.isIntersecting) return;
    var el = e.target; io.unobserve(el);
    var f = JSON.parse(document.getElementById(el.dataset.fig).textContent);
    Plotly.newPlot(el, f.data, f.layout, CFG);
  });
}, {rootMargin: '600px'});
document.querySelectorAll('.chart').forEach(function (el) { io.observe(el); });
document.querySelectorAll('[data-copy]').forEach(function (btn) {
  var label = btn.textContent;
  btn.addEventListener('click', async function () {
    var gd = btn.closest('section').querySelector('.chart');
    try {
      if (!gd.classList.contains('js-plotly-plot')) throw new Error('kuvio ei ole vielä piirretty');
      var url = await Plotly.toImage(gd, {format: 'png', scale: 2});
      var blob = await (await fetch(url)).blob();
      await navigator.clipboard.write([new ClipboardItem({'image/png': blob})]);
      btn.textContent = 'Kopioitu';
    } catch (err) { console.error(err); btn.textContent = 'Kopiointi ei onnistunut'; }
    setTimeout(function () { btn.textContent = label; }, 3000);
  });
});
""" % json.dumps(_PLOTLY_CONFIG)

_CSS = f"""
:root{{--ink:#1f2933;--mut:#6b7280;--line:#e2e6ea;--navy:#0A2A5E;--bg:#f6f7f9}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:{_FONT};color:var(--ink);background:var(--bg);line-height:1.45}}
header{{background:#fff;border-bottom:1px solid var(--line)}}
.wrap{{max-width:1240px;margin:0 auto;padding:0 16px}}
h1{{font-size:22px;color:var(--navy);margin:18px 0 4px}}
h2{{font-size:16px;color:var(--navy);margin:28px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}}
.sub{{color:var(--mut);font-size:13px;margin:0 0 12px}}
nav{{display:flex;flex-wrap:wrap;gap:4px 14px;padding:10px 0 12px;font-size:13px}}
nav .grp{{color:var(--mut);margin-right:-6px}}
nav a{{color:var(--navy);text-decoration:none;padding:2px 0;border-bottom:2px solid transparent}}
nav a:hover,nav a.on{{border-bottom-color:var(--navy)}}
main{{padding:8px 0 40px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,560px),1fr));gap:16px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:6px;padding:10px 12px 8px;overflow:hidden}}
.tools{{display:flex;justify-content:flex-end;height:24px}}
button{{font:inherit;font-size:11px;color:var(--mut);background:#fff;border:1px solid #cfd5db;border-radius:4px;padding:2px 8px;cursor:pointer}}
button:hover{{background:#f1f3f5}}
.note{{font-size:11px;color:var(--mut);margin:4px 2px}}
details{{font-size:11px;color:var(--mut);margin:2px}}
summary{{cursor:pointer}}
table.series{{border-collapse:collapse;margin:6px 0}}
table.series td,table.series th{{padding:2px 12px 2px 0;text-align:left;font-weight:normal}}
.tblwrap{{overflow-x:auto;background:#fff;border:1px solid var(--line);border-radius:6px}}
table.m{{border-collapse:collapse;width:100%;font-size:13px}}
table.m th,table.m td{{padding:6px 10px;border-bottom:1px solid #eef0f2;text-align:right;white-space:nowrap}}
table.m th:first-child,table.m td:first-child{{text-align:left;position:sticky;left:0;background:#fff}}
table.m thead th{{background:#f1f3f5;color:var(--navy)}}
table.m th a{{color:var(--navy);text-decoration:none}}
table.m tr.th td{{background:#f6f7f9;color:var(--navy);font-weight:bold;text-align:left}}
table.m tr.th a{{color:var(--navy);text-decoration:none}}
td.na{{color:#b6bcc3}} td.stale{{color:var(--mut);font-style:italic}}
footer{{color:var(--mut);font-size:12px;padding:0 0 30px}}
"""


def _page(title: str, heading: str, sub: str, nav_html: str, body: str, stamp: str, with_js: bool = True) -> str:
    js = f"<script src=\"plotly.min.js\"></script><script>{_JS}</script>" if with_js else ""
    return f"""<!DOCTYPE html>
<html lang="fi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{_CSS}</style></head>
<body><header><div class="wrap"><h1>{html.escape(heading)}</h1><p class="sub">{html.escape(sub)}</p>{nav_html}</div></header>
<main class="wrap">{body}</main>
<footer class="wrap">Päivitetty {stamp}</footer>{js}</body></html>"""


def _nav(catalog: Catalog, current: str, regions_with_data: set[str], themes_with_data: set[str]) -> str:
    def a(href: str, label: str) -> str:
        on = ' class="on"' if href == current else ""
        return f'<a href="{href}"{on}>{html.escape(label)}</a>'
    parts = [a("index.html", "Yleiskuva"), '<span class="grp">Alueet:</span>']
    parts += [a(f"region_{r.id}.html", r.name) for r in catalog.regions.values() if r.id in regions_with_data]
    parts.append('<span class="grp">Teemat:</span>')
    parts += [a(f"theme_{t}.html", name) for t, name in catalog.themes.items() if t in themes_with_data]
    return "<nav>" + "".join(parts) + "</nav>"


# ------------------------------------------------------------------ sivut

def build_site(
    catalog: Catalog,
    store: Store,
    out_dir: str | Path,
    *,
    now: datetime | None = None,
    write_plotly_js: bool = True,
) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = collect_series(catalog, store)
    stamp = (now or datetime.now()).strftime("%d.%m.%Y %H:%M")
    written: list[Path] = []

    if write_plotly_js:
        from plotly.offline import get_plotlyjs
        p = out / "plotly.min.js"
        p.write_text(get_plotlyjs(), encoding="utf-8")
        written.append(p)

    def get(region: str, indicator: str) -> SeriesData | None:
        return data.get(f"{region}.{indicator}")

    def live(region: str, indicator: str) -> SeriesData | None:
        """Kuviot: vain tuoreet sarjat (vanhentunut sarja näkyy vain yleiskuvan taulukossa kursiivina)."""
        sd = data.get(f"{region}.{indicator}")
        return None if sd is None or sd.info.get("stale") else sd

    regions_with = {sd.sdef.region for sd in data.values()}
    themes_with = {catalog.indicators[sd.sdef.indicator].theme for sd in data.values()}
    refs = [r for r in catalog.regions.values() if r.ref]

    def nav(current: str) -> str:
        return _nav(catalog, current, regions_with, themes_with)

    # -- aluesivut
    for reg in catalog.regions.values():
        if reg.id not in regions_with:
            continue
        cards: list[str] = []
        body: list[str] = []
        n = 0
        for tid, tname in catalog.themes.items():
            sect: list[str] = []
            for ind in catalog.indicators.values():
                if ind.theme != tid:
                    continue
                main = live(reg.id, ind.id)
                if main is None:
                    continue
                items = [(main, reg, True)]
                bars = ind.kind == "bar"
                if not bars:
                    items += [(r_sd, r, False) for r in refs if r.id != reg.id
                              if (r_sd := live(r.id, ind.id)) is not None]
                fig = _figure(ind, items, title=f"{ind.title}, {reg.name}", as_bars=bars)
                n += 1
                sect.append(_card(n, fig, ind, items))
            if sect:
                body.append(f'<h2>{html.escape(tname)}</h2><div class="grid">{"".join(sect)}</div>')
        path = out / f"region_{reg.id}.html"
        path.write_text(_page(f"{reg.name} – makroseuranta", reg.name,
                              "Alueen indikaattorit; katkoviiva = viitealueet (euroalue, USA).",
                              nav(path.name), "".join(body), stamp), encoding="utf-8")
        written.append(path)

    # -- teemasivut (maavertailu)
    for tid, tname in catalog.themes.items():
        if tid not in themes_with:
            continue
        sect = []
        n = 0
        for ind in catalog.indicators.values():
            if ind.theme != tid:
                continue
            items = [(sd, reg, True) for reg in catalog.regions.values() if (sd := live(reg.id, ind.id)) is not None]
            if not items:
                continue
            fig = _figure(ind, items, title=ind.title, as_bars=False)
            n += 1
            sect.append(_card(n, fig, ind, items))
        path = out / f"theme_{tid}.html"
        path.write_text(_page(f"{tname} – maavertailu", tname, "Kaikki alueet samassa kuviossa.",
                              nav(path.name), f'<div class="grid">{"".join(sect)}</div>', stamp), encoding="utf-8")
        written.append(path)

    # -- yleiskuva: viimeisimmät arvot
    cols = [r for r in catalog.regions.values() if r.id in regions_with]
    head = "".join(f'<th><a href="region_{r.id}.html">{html.escape(r.name)}</a></th>' for r in cols)
    rows: list[str] = []
    for tid, tname in catalog.themes.items():
        inds = [i for i in catalog.indicators.values() if i.theme == tid]
        if not any(get(r.id, i.id) for i in inds for r in cols):
            continue
        rows.append(f'<tr class="th"><td colspan="{len(cols) + 1}"><a href="theme_{tid}.html">{html.escape(tname)}</a></td></tr>')
        for ind in inds:
            cells = []
            for r in cols:
                sd = get(r.id, ind.id)
                if sd is None:
                    cells.append('<td class="na">\u2013</td>')
                    continue
                tip = f"{_period_label(sd.s.index[-1], sd.info['freq'])}; {sd.info['source']}:{sd.info['code']}"
                cls = ' class="stale"' if sd.info.get("stale") else ""
                cells.append(f'<td{cls} title="{html.escape(tip)}">{_fmt(float(sd.s.iloc[-1]), ind.decimals)}</td>')
            rows.append(f"<tr><td>{html.escape(ind.title)} <span style=\"color:#9aa1a9\">({html.escape(ind.unit)})</span></td>{''.join(cells)}</tr>")
    missing = [sd.id for sd in catalog.series if sd.id not in data]
    miss_html = (
        f'<details style="margin-top:14px"><summary>Puuttuvat sarjat ({len(missing)} / {len(catalog.series)})</summary>'
        f'<p class="note">{html.escape(", ".join(missing))}</p></details>' if missing else ""
    )
    body_idx = (f'<div class="tblwrap"><table class="m"><thead><tr><th>Indikaattori</th>{head}</tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div>'
                f'<p class="note">Viimeisin saatavilla oleva havainto; vie hiiri arvon päälle nähdäksesi jakson ja lähteen. '
                f'Kursiivi = data yli 18 kk vanha.</p>{miss_html}')
    path = out / "index.html"
    path.write_text(_page("Makroseuranta", "Makroseuranta", f"{len(data)} sarjaa, {len(cols)} aluetta",
                          nav("index.html"), body_idx, stamp, with_js=False), encoding="utf-8")
    written.append(path)
    return written
