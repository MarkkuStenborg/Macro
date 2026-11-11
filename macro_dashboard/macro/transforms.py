# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\macro\transforms.py
"""Sarjamuunnokset. Tallennettu sarja on aina lähteen alkuperäinen; muunnos tehdään sivua rakennettaessa.

* ``yoy`` : prosenttimuutos vuodentakaisesta (kk: 12, neljännesvuosi: 4, vuosi: 1)
* ``pch`` : prosenttimuutos edellisestä jaksosta (m/m, q/q)
* ``diff``: absoluuttinen muutos edellisestä jaksosta
"""

from __future__ import annotations

import pandas as pd

from data_fetchers import Frequency

__all__ = ["apply_transform", "TRANSFORMS"]

_PER_YEAR = {Frequency.MONTHLY: 12, Frequency.QUARTERLY: 4, Frequency.ANNUAL: 1}
TRANSFORMS = ("yoy", "pch", "diff")


def _regular(s: pd.Series, freq: Frequency) -> pd.Series:
    """Täysi säännöllinen aikaindeksi, jotta viiveet vastaavat jaksoja."""
    s = s.dropna()
    if s.empty:
        return s
    return s.asfreq(freq.pandas_freq)


def apply_transform(s: pd.Series, post: str | None, freq: Frequency) -> pd.Series:
    if not post:
        return s.dropna()
    if post not in TRANSFORMS:
        raise ValueError(f"Tuntematon muunnos {post!r}; sallitut: {TRANSFORMS}")
    r = _regular(s, freq)
    if r.empty:
        return r
    if post == "yoy":
        if freq not in _PER_YEAR:
            raise ValueError("yoy vaatii kk-, nelj.vuosi- tai vuositaajuuden")
        out = r.pct_change(_PER_YEAR[freq], fill_method=None) * 100.0
    elif post == "pch":
        out = r.pct_change(1, fill_method=None) * 100.0
    else:
        out = r.diff()
    return out.dropna()
