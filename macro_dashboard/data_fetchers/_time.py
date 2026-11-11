# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\_time.py
"""Aikakoodien jäsennys ja muotoilu, jaettu kaikille hakijoille.

Tunnetut muodot (kuukausi / kvartaali / vuosi):
* Eurostat, OECD : ``2024-03`` / ``2024-Q1`` / ``2024``
* IMF            : ``2024-M03`` / ``2024-Q1`` / ``2024``
* Tilastokeskus  : ``2024M03`` / ``2024Q1`` / ``2024``
"""

from __future__ import annotations

import re

import pandas as pd

from .base import Frequency

__all__ = ["period_str", "normalize_time_label", "parse_time_labels"]


def period_str(ts: pd.Timestamp, freq: Frequency) -> str:
    """sinceTimePeriod/startPeriod-muoto taajuuden mukaan (``2024-03``, ``2024-Q1``, ``2024``)."""
    if freq is Frequency.MONTHLY:
        return ts.strftime("%Y-%m")
    if freq is Frequency.QUARTERLY:
        return f"{ts.year}-Q{(ts.month - 1) // 3 + 1}"
    if freq is Frequency.ANNUAL:
        return str(ts.year)
    return ts.strftime("%Y-%m-%d")


def normalize_time_label(label: str, freq: Frequency) -> str:
    label = str(label).strip()
    if freq is Frequency.MONTHLY:
        m = re.fullmatch(r"(\d{4})-?M(\d{1,2})", label)
        if m:
            return f"{m[1]}-{int(m[2]):02d}"
    elif freq is Frequency.QUARTERLY:
        m = re.fullmatch(r"(\d{4})-?Q([1-4])", label)
        if m:
            return f"{m[1]}Q{m[2]}"
    return label


def parse_time_labels(labels, freq: Frequency) -> pd.DatetimeIndex:
    """Muunna aikakoodit jakson ALKUHETKIKSI."""
    norm = [normalize_time_label(s, freq) for s in labels]
    if freq is Frequency.QUARTERLY:
        return pd.PeriodIndex(norm, freq="Q").to_timestamp(how="start")
    if freq is Frequency.MONTHLY:
        return pd.PeriodIndex(norm, freq="M").to_timestamp(how="start")
    if freq is Frequency.ANNUAL:
        return pd.PeriodIndex(norm, freq="Y").to_timestamp(how="start")
    return pd.DatetimeIndex(pd.to_datetime(norm))
