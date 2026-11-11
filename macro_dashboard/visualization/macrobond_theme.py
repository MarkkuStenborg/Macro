# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\visualization\macrobond_theme.py
"""Macrobond-tyylinen Plotly-pohja.

Sisältö
-------
* ``MACROBOND_LAYOUT``   : tyylimäärittely dictionaryna (layout-osa).
* ``MACROBOND_TEMPLATE`` : sama ``plotly.graph_objects.layout.Template``-oliona;
                           rekisteröity nimellä ``"macrobond"``.
* ``apply_macrobond_style`` : pieni apufunktio asioihin, joita templatella ei
  voi tehdä: otsikko ja lähde kuvion SISÄLLE, kuukausi/vuosi-akselin
  tekstit sekä vasen/oikea y-akseli.

Värit ovat arvioita Macrobondin ulkoasusta, eivät virallisia arvoja.
Verdana on oltava asennettuna katselukoneelle (Windowsissa on); muuten
selain käyttää varafonttia.

Käyttö::

    import plotly.graph_objects as go
    from visualization.macrobond_theme import apply_macrobond_style

    fig = go.Figure([go.Scatter(x=x, y=a, name="BKT"),
                     go.Scatter(x=x, y=b, name="Työttömyys")])
    apply_macrobond_style(fig, title="Suomen talous", subtitle="Indeksi, 2015=100",
                          source="Eurostat, Tilastokeskus",
                          left_title="BKT", right_title="Työttömyys, %",
                          right=["Työttömyys"])
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

__all__ = [
    "PALETTE",
    "MACROBOND_LAYOUT",
    "MACROBOND_TEMPLATE",
    "make_date_ticks",
    "apply_macrobond_style",
]

# --- värit ---------------------------------------------------------------
DARK_BLUE = "#0A2A5E"  # ensisijainen
GRAY = "#7F8790"  # toissijainen
ACCENT_RED = "#C8102E"
ACCENT_ORANGE = "#E08A00"
ACCENT_TEAL = "#1B998B"
ACCENT_LIGHT_BLUE = "#4A90D9"
ACCENT_GREEN = "#5B8C2A"

PALETTE = [
    DARK_BLUE,
    GRAY,
    ACCENT_RED,
    ACCENT_ORANGE,
    ACCENT_TEAL,
    ACCENT_LIGHT_BLUE,
    ACCENT_GREEN,
]

TEXT = "#333333"
GRID = "rgba(0, 0, 0, 0.07)"  # hyvin hento vaakaruudukko
AXIS_LINE = "#9AA0A6"
ZERO_LINE = "#B5BAC0"

FONT_FAMILY = "Verdana, Geneva, 'DejaVu Sans', sans-serif"

# --- tyylimäärittely -----------------------------------------------------
_MARGIN_B = 95  # alamarginaali: aika-akseli + selite/lähde-rivi

_YAXIS_COMMON = dict(
    showline=False,
    ticks="",
    tickfont=dict(size=11),
    automargin=True,
)

MACROBOND_LAYOUT: dict = dict(
    font=dict(family=FONT_FAMILY, size=12, color=TEXT),
    colorway=PALETTE,
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(l=60, r=60, t=90, b=_MARGIN_B),
    hovermode="x unified",
    hoverlabel=dict(font=dict(family=FONT_FAMILY, size=11)),
    title=dict(
        x=0,
        xanchor="left",
        y=0.97,
        yanchor="top",
        font=dict(size=16, color=DARK_BLUE),
    ),
    # selitteet kuvion alareunaan (vasemmalle); lähde jakaa saman rivin oikealla
    legend=dict(
        orientation="h",
        xref="paper",
        x=0,
        xanchor="left",
        yref="container",
        y=0,
        yanchor="bottom",
        bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
    ),
    xaxis=dict(
        showgrid=False,  # ei pystyruudukkoa
        zeroline=False,
        showline=True,
        linecolor=AXIS_LINE,
        linewidth=1,
        ticks="outside",
        ticklen=4,
        tickcolor=AXIS_LINE,
        tickfont=dict(size=11),
        automargin=True,
        hoverformat="%-m/%Y",  # vihjelaatikon aika: kuukausi/vuosi numeroina
        # oletus ilman apufunktiota: kuukausi numerona, tätä harvemmin vuosi
        tickformatstops=[
            dict(dtickrange=[None, "M12"], value="%-m"),
            dict(dtickrange=["M12", None], value="%Y"),
        ],
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor=GRID,
        gridwidth=1,
        zeroline=True,
        zerolinecolor=ZERO_LINE,
        zerolinewidth=1,
        **_YAXIS_COMMON,
    ),
    # oikea akseli: ei omaa ruudukkoa (vältetään kaksi ristiin menevää ruudukkoa)
    yaxis2=dict(
        showgrid=False,
        zeroline=False,
        **_YAXIS_COMMON,
    ),
)

MACROBOND_TEMPLATE = go.layout.Template(
    layout=MACROBOND_LAYOUT,
    data=dict(
        scatter=[go.Scatter(line=dict(width=2))],
        bar=[go.Bar(marker=dict(line=dict(width=0)))],
    ),
)

pio.templates["macrobond"] = MACROBOND_TEMPLATE


# --- apufunktiot ---------------------------------------------------------
def make_date_ticks(start, end) -> tuple[list, list[str]]:
    """Väljä Macrobond-tyylinen aika-akseli.

    Kuukaudet numeroina 1-12; vuosi näkyy vain tammikuun kohdalla.
    Pitkillä aikaväleillä siirrytään kvartaaleihin (1,4,7,10), vuosiin
    ja lopulta viiden vuoden väliin.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if months <= 30:
        step = 1
    elif months <= 72:
        step = 3
    elif months <= 180:
        step = 12
    else:
        step = 60

    if step < 12:
        m = ((start.month - 1) // step) * step + 1
        first = pd.Timestamp(year=start.year, month=m, day=1)
        if first < start:
            first += pd.DateOffset(months=step)
        vals = pd.date_range(first, end, freq=pd.DateOffset(months=step))
        texts = [f"{d.month}<br>{d.year}" if d.month == 1 else f"{d.month}" for d in vals]
    else:
        ystep = step // 12
        y0 = -(-start.year // ystep) * ystep  # pyöristys ylös ystepin kerrannaiseen
        first = pd.Timestamp(year=y0, month=1, day=1)
        if first < start:
            first += pd.DateOffset(years=ystep)
        vals = pd.date_range(first, end, freq=pd.DateOffset(years=ystep))
        texts = [str(d.year) for d in vals]
    return [d.to_pydatetime() for d in vals], texts


def _trace_x_range(fig: go.Figure):
    mins, maxs = [], []
    for tr in fig.data:
        if tr.x is None or len(tr.x) == 0:
            continue
        x = pd.to_datetime(pd.Index(tr.x))
        mins.append(x.min())
        maxs.append(x.max())
    if not mins:
        return None
    return min(mins), max(maxs)


def apply_macrobond_style(
    fig: go.Figure,
    *,
    title: str,
    subtitle: str | None = None,
    source: str | None = None,
    left_title: str | None = None,
    right_title: str | None = None,
    right: Iterable[int | str] = (),
    date_ticks: bool = True,
    x_range: tuple | None = None,
) -> go.Figure:
    """Levitä Macrobond-tyyli kuvioon.

    Parameters
    ----------
    title, subtitle : kuvion sisälle piirrettävä otsikko, jotta se tulee mukaan
        kuvaa kopioitaessa/vietäessä.
    source : lähde oikeaan alareunaan pienellä fontilla.
    right : oikealle akselille (y2) siirrettävät trace-nimet tai -indeksit.
        Tyhjä -> kaikki vasemmalla ja oikealle piirretään peilattu akseli
        (samat arvot molemmin puolin).
    left_title, right_title : akselien otsikot (yksikkö/muuttuja). Kahden
        akselin tilassa värjätään ensimmäisen sarjan värillä.
    date_ticks : käytä ``make_date_ticks``-akselia (vain aika-akselille).
    x_range : (alku, loppu); oletuksena datan ääriarvot.
    """
    fig.update_layout(template=MACROBOND_TEMPLATE)

    # Värit eksplisiittisesti, jotta akselit voidaan värjätä sarjan mukaan
    colors: list[str] = []
    for i, tr in enumerate(fig.data):
        c = PALETTE[i % len(PALETTE)]
        if tr.type == "bar":
            c = tr.marker.color or c
            tr.marker.color = c
        elif tr.type == "scatter":
            c = tr.line.color or c
            tr.line.color = c
        colors.append(c)

    right_set = set(right)
    for i, tr in enumerate(fig.data):
        if i in right_set or tr.name in right_set:
            tr.yaxis = "y2"

    dual = any(tr.yaxis == "y2" for tr in fig.data)

    # Aika-akseli (lasketaan ennen mahdollista apusarjaa)
    if date_ticks:
        rng = x_range or _trace_x_range(fig)
        if rng is not None:
            try:
                vals, texts = make_date_ticks(*rng)
            except (TypeError, ValueError):
                vals = []
            if vals:
                fig.update_xaxes(
                    tickmode="array",
                    tickvals=vals,
                    ticktext=texts,
                    range=[pd.Timestamp(rng[0]), pd.Timestamp(rng[1])],
                )

    # Y-akselit: vasen + oikea
    y2 = dict(overlaying="y", side="right")
    if not dual:
        # Ei oikean akselin sarjoja: peilataan vasen akseli oikealle apusarjalla
        y2["matches"] = "y"
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                yaxis="y2",
                mode="lines",
                showlegend=False,
                hoverinfo="skip",
            )
        )
    fig.update_layout(yaxis2=y2)

    def _axis_style(text, color):
        d: dict = {}
        if text:
            d["title"] = dict(text=text, font=dict(color=color or TEXT, size=11), standoff=8)
        if color:
            d["tickfont"] = dict(color=color, size=11)
        return d

    left_color = colors[0] if dual and colors else None
    right_color = next(
        (c for tr, c in zip(fig.data, colors) if tr.yaxis == "y2"), None
    ) if dual else None
    fig.update_layout(
        yaxis=_axis_style(left_title, left_color),
        yaxis2=_axis_style(right_title if dual else (right_title or left_title), right_color),
    )

    # Otsikko kuvion sisään
    text = f"<b>{title}</b>"
    if subtitle:
        text += f"<br><span style='font-size:12px;color:{GRAY}'>{subtitle}</span>"
    fig.update_layout(
        title=dict(text=text),
        margin=dict(t=100 if subtitle else 80),
    )

    # Lähde oikeaan alareunaan, pieni fontti
    if source:
        fig.add_annotation(
            text=f"Lähde: {source}",
            xref="paper",
            yref="paper",
            x=1,
            y=0,
            xanchor="right",
            yanchor="bottom",
            yshift=-(_MARGIN_B - 6),  # kuvion alareunaan, samalle riville selitteen kanssa
            showarrow=False,
            font=dict(size=9, color=GRAY),
        )
    return fig
