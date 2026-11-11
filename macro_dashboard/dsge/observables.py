# ============================================================================
# File: macro_dashboard/dsge/observables.py
# Layer: DSGE
# Purpose: Definitions of DSGE observables
# ============================================================================

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Observable:
    series_id: str
    observable: str
    source: str
    frequency: str
    transform: str
    description: str


OBSERVABLES: Dict[str, Observable] = {

    # REAL ACTIVITY

    "GDP_FI": Observable(
        series_id="GDP_FI",
        observable="output_growth",
        source="Eurostat",
        frequency="Q",
        transform="logdiff",
        description="Finland GDP"
    ),

    "GDP_EA": Observable(
        series_id="GDP_EA",
        observable="output_growth",
        source="Eurostat",
        frequency="Q",
        transform="logdiff",
        description="Euro Area GDP"
    ),

    "GDP_US": Observable(
        series_id="GDP_US",
        observable="output_growth",
        source="FRED",
        frequency="Q",
        transform="logdiff",
        description="US GDP"
    ),

    # INFLATION

    "HICP_FI": Observable(
        series_id="HICP_FI",
        observable="inflation",
        source="Eurostat",
        frequency="M",
        transform="yoy",
        description="Finland HICP"
    ),

    "HICP_EA": Observable(
        series_id="HICP_EA",
        observable="inflation",
        source="Eurostat",
        frequency="M",
        transform="yoy",
        description="Euro Area HICP"
    ),

    "CPI_US": Observable(
        series_id="CPI_US",
        observable="inflation",
        source="FRED",
        frequency="M",
        transform="yoy",
        description="US CPI"
    ),

    # LABOUR MARKET

    "UNRATE_FI": Observable(
        series_id="UNRATE_FI",
        observable="labor_slack",
        source="Eurostat",
        frequency="M",
        transform="level",
        description="Finland unemployment"
    ),

    "UNRATE_EA": Observable(
        series_id="UNRATE_EA",
        observable="labor_slack",
        source="Eurostat",
        frequency="M",
        transform="level",
        description="Euro Area unemployment"
    ),

    "UNRATE_US": Observable(
        series_id="UNRATE_US",
        observable="labor_slack",
        source="FRED",
        frequency="M",
        transform="level",
        description="US unemployment"
    ),

    # POLICY RATES

    "ECB_RATE": Observable(
        series_id="ECB_RATE",
        observable="policy_rate",
        source="ECB",
        frequency="M",
        transform="level",
        description="ECB policy rate"
    ),

    "FEDFUNDS": Observable(
        series_id="FEDFUNDS",
        observable="policy_rate",
        source="FRED",
        frequency="M",
        transform="level",
        description="Fed Funds"
    ),

    # RISK

    "VIX": Observable(
        series_id="VIX",
        observable="financial_stress",
        source="FRED",
        frequency="D",
        transform="level",
        description="VIX"
    ),

    # ENERGY

    "BRENT": Observable(
        series_id="BRENT",
        observable="oil_price_shock",
        source="FRED",
        frequency="D",
        transform="logdiff",
        description="Brent crude"
    ),

    # GLOBAL

    "WORLD_TRADE": Observable(
        series_id="WORLD_TRADE",
        observable="external_demand",
        source="CPB",
        frequency="M",
        transform="yoy",
        description="World trade"
    ),

    # CHINA

    "CHINA_CPI": Observable(
        series_id="CHINA_CPI",
        observable="china_inflation",
        source="FRED",
        frequency="M",
        transform="yoy",
        description="China CPI"
    ),

    "CHINA_IP": Observable(
        series_id="CHINA_IP",
        observable="china_activity",
        source="FRED",
        frequency="M",
        transform="yoy",
        description="China industrial production"
    ),
}


def get_observable(series_id: str) -> Observable:
    return OBSERVABLES[series_id]


def list_observables():
    return sorted(OBSERVABLES.keys())


def validate_observables() -> None:

    if len(OBSERVABLES) == 0:
        raise ValueError("No observables defined")

    for key, obs in OBSERVABLES.items():

        if key != obs.series_id:
            raise ValueError(
                f"Key mismatch: {key} != {obs.series_id}"
            )


if __name__ == "__main__":

    validate_observables()

    print(
        f"OK - loaded {len(OBSERVABLES)} observables"
    )