# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\base.py
"""Kantaluokka ja kanoninen datamuoto kaikille data_fetchers-alimoduuleille.

Kanoninen muoto (``CanonicalFrame``)
------------------------------------
* ``pd.DataFrame``, leveä muoto: yksi sarake per sarja.
* Indeksi: ``pd.DatetimeIndex``, nimi ``"date"``, tz-naiivi, nouseva, uniikki,
  jakson ALKUHETKI (D, MS, QS, YS) ja ``freq`` asetettu.
* Sarakkeet: kanoniset ``series_id``-merkkijonot (``SeriesSpec.series_id``),
  dtype ``float64``, puuttuva arvo = ``NaN``.
* Yksi taajuus per DataFrame (``FetchRequest.frequency``); eri taajuudet
  haetaan erillisillä kutsuilla ja yhdistetään kutsujan päässä.
* Metadata: ``df.attrs["source"]``, ``df.attrs["retrieved_at"]``,
  ``df.attrs["series"]`` (dict ``series_id -> SeriesSpec``).
  Huom: ``attrs`` ei säily kaikissa pandas-operaatioissa; ne ovat
  tietolähteen jäljitettävyyttä varten, eivät laskennan syötteeksi.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Mapping, Sequence

import pandas as pd

__all__ = [
    "CanonicalFrame",
    "Frequency",
    "SeriesSpec",
    "FetchRequest",
    "FetcherError",
    "FetchError",
    "SchemaError",
    "BaseFetcher",
    "validate_canonical",
    "INDEX_NAME",
]

CanonicalFrame = pd.DataFrame  # tyyppialias dokumentaatiota varten
INDEX_NAME = "date"


class FetcherError(Exception):
    """Kaikkien data_fetchers-virheiden juuri."""


class FetchError(FetcherError):
    """Haku lähteestä epäonnistui (verkko, autentikointi, tuntematon sarja)."""


class SchemaError(FetcherError):
    """Palautettu data ei täytä kanonista muotoa."""


class Frequency(str, Enum):
    DAILY = "D"
    MONTHLY = "M"
    QUARTERLY = "Q"
    ANNUAL = "A"

    @property
    def pandas_freq(self) -> str:
        """Jakson alkuhetkeen ankkuroitu pandas-taajuus."""
        return {"D": "D", "M": "MS", "Q": "QS", "A": "YS"}[self.value]


@dataclass(frozen=True)
class SeriesSpec:
    """Yksittäisen sarjan kuvaus; ``series_id`` on kanoninen sarakenimi."""

    series_id: str  # esim. "FI.gdp_real.q"
    source_code: str  # lähteen oma koodi (Eurostat-dataset+filtterit, IMF-indikaattori)
    frequency: Frequency
    geo: str | None = None  # ISO 3166-1 alpha-2/alpha-3, sovittava yhteen
    unit: str | None = None
    seasonal_adjustment: str | None = None  # "SA" | "NSA" | "CA"
    description: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)  # lähdekohtaiset parametrit


@dataclass(frozen=True)
class FetchRequest:
    series: Sequence[SeriesSpec]
    start: pd.Timestamp | None = None
    end: pd.Timestamp | None = None

    @property
    def frequency(self) -> Frequency:
        freqs = {s.frequency for s in self.series}
        if len(freqs) != 1:
            raise SchemaError(
                f"Yhden haun sarjoilla on oltava sama taajuus, saatiin {sorted(f.value for f in freqs)}"
            )
        return next(iter(freqs))


def validate_canonical(df: pd.DataFrame, request: FetchRequest) -> None:
    """Nostaa ``SchemaError``in, jos ``df`` ei täytä kanonista muotoa."""
    if not isinstance(df.index, pd.DatetimeIndex):
        raise SchemaError("Indeksin on oltava DatetimeIndex")
    if df.index.name != INDEX_NAME:
        raise SchemaError(f"Indeksin nimen on oltava {INDEX_NAME!r}")
    if df.index.tz is not None:
        raise SchemaError("Indeksin on oltava tz-naiivi")
    if not df.index.is_monotonic_increasing or not df.index.is_unique:
        raise SchemaError("Indeksin on oltava nouseva ja uniikki")
    expected = [s.series_id for s in request.series]
    if list(df.columns) != expected:
        raise SchemaError(f"Sarakkeet {list(df.columns)} != pyydetyt {expected}")
    bad = [c for c, t in df.dtypes.items() if t != "float64"]
    if bad:
        raise SchemaError(f"Sarakkeiden dtype on oltava float64: {bad}")
    if len(df) and df.index.freq is None:
        raise SchemaError("Indeksin freq on asetettava (käytä asfreq)")


class BaseFetcher(ABC):
    """Kaikkien lähdekohtaisten hakijoiden kantaluokka.

    Julkinen rajapinta on ``fetch``; sitä EI ylikirjoiteta (template method).
    Alaluokka toteuttaa vain ``_fetch_raw``, ``_to_canonical`` ja
    ``get_metadata``. Normalisointi (indeksi, dtype, rajaus, attrs) ja
    validointi tehdään kantaluokassa, jotta muoto on identtinen lähteestä
    riippumatta.
    """

    #: Rekisterin avain, esim. "eurostat" / "imf". Pakollinen konkreettisille luokille.
    source_name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "__abstractmethods__", None) and "source_name" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} must define class attribute 'source_name'")

    # -- julkinen API -----------------------------------------------------

    def fetch(self, request: FetchRequest) -> CanonicalFrame:
        freq = request.frequency  # validoi yhden taajuuden säännön
        raw = self._fetch_raw(request)
        df = self._to_canonical(raw, request)
        df = self._finalize(df, request, freq)
        validate_canonical(df, request)
        return df

    @abstractmethod
    def get_metadata(self, source_code: str) -> SeriesSpec:
        """Hae yksittäisen sarjan metadata lähteestä (ei arvoja)."""

    # -- alaluokan toteutettavat ------------------------------------------

    @abstractmethod
    def _fetch_raw(self, request: FetchRequest) -> Any:
        """Hae lähteen natiivi vastaus (JSON, SDMX, DataFrame, ...).

        Nostaa ``FetchError``in epäonnistuessaan. Ei normalisointia.
        """

    @abstractmethod
    def _to_canonical(self, raw: Any, request: FetchRequest) -> pd.DataFrame:
        """Muunna natiivi vastaus leveäksi DataFrameksi.

        Vaatimus: sarakkeet = ``series_id``t, indeksi = DatetimeIndex
        (mikä tahansa jaksoankkurointi; ``_finalize`` normalisoi).
        """

    # -- kantaluokan yhteinen normalisointi -------------------------------

    def _finalize(
        self, df: pd.DataFrame, request: FetchRequest, freq: Frequency
    ) -> pd.DataFrame:
        out = df.copy()
        if isinstance(out.index, pd.PeriodIndex):
            out.index = out.index.to_timestamp(how="start")
        out.index = pd.DatetimeIndex(out.index)
        if out.index.tz is not None:
            out.index = out.index.tz_convert(None)
        out.index.name = INDEX_NAME
        out = out.reindex(columns=[s.series_id for s in request.series])
        out = out.astype("float64").sort_index()
        out = out[~out.index.duplicated(keep="last")]
        if request.start is not None:
            out = out.loc[out.index >= request.start]
        if request.end is not None:
            out = out.loc[out.index <= request.end]
        if len(out):
            out = out.asfreq(freq.pandas_freq)
        out.attrs.update(
            source=self.source_name,
            retrieved_at=pd.Timestamp.now(tz="UTC").isoformat(),
            series={s.series_id: s for s in request.series},
        )
        return out