# ============================================================================
# File: macro_dashboard/data_fetchers/__init__.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\__init__.py
"""data_fetchers: yhtenäinen rajapinta makrotaloudellisen datan hakuun.

Käyttö::

    from data_fetchers import get_fetcher, FetchRequest, SeriesSpec, Frequency

    fetcher = get_fetcher("eurostat")
    df = fetcher.fetch(FetchRequest(series=[SeriesSpec(...)]))

Kaikki lähteet palauttavat saman kanonisen muodon (ks. ``base.py``).
Alimoduulit ladataan laiskasti, jotta esim. IMF-riippuvuuksia ei vaadita
Eurostat-käyttöön.
"""

from __future__ import annotations

from importlib import import_module
from typing import Sequence, TypeVar

import pandas as pd

from ._http import HttpClient
from .base import (
    INDEX_NAME,
    BaseFetcher,
    CanonicalFrame,
    FetchError,
    FetcherError,
    FetchRequest,
    Frequency,
    SchemaError,
    SeriesSpec,
    validate_canonical,
)

__all__ = [
    "INDEX_NAME",
    "BaseFetcher",
    "CanonicalFrame",
    "FetchError",
    "FetcherError",
    "FetchRequest",
    "Frequency",
    "SchemaError",
    "SeriesSpec",
    "validate_canonical",
    "register",
    "get_fetcher",
    "available_sources",
    "fetch_series",
    "HttpClient",
]

F = TypeVar("F", bound=type[BaseFetcher])

_REGISTRY: dict[str, type[BaseFetcher]] = {}

# source_name -> moduuli, joka rekisteröi luokkansa tuonnissa (@register)
_LAZY_MODULES: dict[str, str] = {
    "eurostat": f"{__name__}.eurostat_fetcher",
    "imf": f"{__name__}.imf_fetcher",
    "fred": f"{__name__}.fred_fetcher",
    "oecd": f"{__name__}.oecd_fetcher",
    "statfin": f"{__name__}.statfin_fetcher",
    "bundesbank": f"{__name__}.bundesbank_fetcher",
    "suomenpankki": f"{__name__}.suomenpankki_fetcher",
    "worldbank": f"{__name__}.worldbank_fetcher",
    "dbnomics": f"{__name__}.dbnomics_fetcher",
}

# vaihtoehtoiset nimet -> rekisteröity source_name
_ALIASES: dict[str, str] = {"tilastokeskus": "statfin"}


def register(cls: F) -> F:
    """Luokkadekoraattori: rekisteröi hakijan ``source_name``-avaimella."""
    name = cls.source_name
    if name in _REGISTRY and _REGISTRY[name] is not cls:
        raise FetcherError(f"Lähde {name!r} on jo rekisteröity")
    _REGISTRY[name] = cls
    return cls


def get_fetcher(source: str, **kwargs) -> BaseFetcher:
    """Palauta alustettu hakija lähteen nimellä; ``kwargs`` välitetään konstruktorille."""
    source = _ALIASES.get(source, source)
    if source not in _REGISTRY:
        module = _LAZY_MODULES.get(source)
        if module is None:
            raise FetcherError(
                f"Tuntematon lähde {source!r}; saatavilla: {available_sources()}"
            )
        import_module(module)
        if source not in _REGISTRY:
            raise FetcherError(f"Moduuli {module} ei rekisteröinyt lähdettä {source!r}")
    return _REGISTRY[source](**kwargs)


def available_sources() -> list[str]:
    return sorted(set(_REGISTRY) | set(_LAZY_MODULES) | set(_ALIASES))


def fetch_series(
    source: str,
    series: Sequence[SeriesSpec],
    start: pd.Timestamp | str | None = None,
    end: pd.Timestamp | str | None = None,
    **fetcher_kwargs,
) -> CanonicalFrame:
    """Yhteinen sisäänkäynti: hae sarjat lähteestä kanonisessa muodossa.

    ``fetcher_kwargs`` (esim. ``api_key`` FRED:lle, tyypillisesti ``config.py``:stä)
    välitetään hakijan konstruktorille.
    """
    request = FetchRequest(
        series=list(series),
        start=pd.Timestamp(start) if start is not None else None,
        end=pd.Timestamp(end) if end is not None else None,
    )
    return get_fetcher(source, **fetcher_kwargs).fetch(request)
