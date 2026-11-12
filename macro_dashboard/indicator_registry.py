# ============================================================================
# File: macro_dashboard/indicator_registry.py
# Layer: Dashboard
# Purpose: Master registry of all dashboard indicators
# ============================================================================

from dataclasses import dataclass


@dataclass(frozen=True)
class Indicator:

    code: str

    group: str

    section: str

    display_name: str

    frequency: str

    source: str

    unit: str

    dashboard: bool = True


INDICATORS = {

    #
    # FINLAND
    #

    "GDP_FI": Indicator(
        code="GDP_FI",
        group="Finland",
        section="Growth",
        display_name="GDP Growth",
        frequency="Q",
        source="Eurostat",
        unit="%"
    ),

    "HICP_FI": Indicator(
        code="HICP_FI",
        group="Finland",
        section="Inflation",
        display_name="Inflation",
        frequency="M",
        source="Eurostat",
        unit="%"
    ),

    "UNRATE_FI": Indicator(
        code="UNRATE_FI",
        group="Finland",
        section="Labour",
        display_name="Unemployment",
        frequency="M",
        source="Eurostat",
        unit="%"
    ),

    "FI_10Y": Indicator(
        code="FI_10Y",
        group="Finland",
        section="Rates",
        display_name="10Y Government Bond",
        frequency="D",
        source="Bank of Finland",
        unit="%"
    ),

    #
    # EURO AREA
    #

    "GDP_EA": Indicator(
        code="GDP_EA",
        group="Euro Area",
        section="Growth",
        display_name="GDP Growth",
        frequency="Q",
        source="Eurostat",
        unit="%"
    ),

    "HICP_EA": Indicator(
        code="HICP_EA",
        group="Euro Area",
        section="Inflation",
        display_name="Inflation",
        frequency="M",
        source="Eurostat",
        unit="%"
    ),

    "ECB_RATE": Indicator(
        code="ECB_RATE",
        group="Euro Area",
        section="Rates",
        display_name="ECB Deposit Rate",
        frequency="M",
        source="ECB",
        unit="%"
    ),

    #
    # USA
    #

    "GDP_US": Indicator(
        code="GDP_US",
        group="USA",
        section="Growth",
        display_name="GDP Growth",
        frequency="Q",
        source="FRED",
        unit="%"
    ),

    "CPI_US": Indicator(
        code="CPI_US",
        group="USA",
        section="Inflation",
        display_name="Inflation",
        frequency="M",
        source="FRED",
        unit="%"
    ),

    "UNRATE_US": Indicator(
        code="UNRATE_US",
        group="USA",
        section="Labour",
        display_name="Unemployment",
        frequency="M",
        source="FRED",
        unit="%"
    ),

    #
    # CHINA
    #

    "CHINA_IP": Indicator(
        code="CHINA_IP",
        group="China",
        section="Growth",
        display_name="Industrial Production",
        frequency="M",
        source="FRED",
        unit="%"
    ),

    "CHINA_CPI": Indicator(
        code="CHINA_CPI",
        group="China",
        section="Inflation",
        display_name="Inflation",
        frequency="M",
        source="FRED",
        unit="%"
    ),

    #
    # GLOBAL
    #

    "BRENT": Indicator(
        code="BRENT",
        group="Global",
        section="Energy",
        display_name="Brent Oil",
        frequency="D",
        source="FRED",
        unit="USD"
    ),

    "VIX": Indicator(
        code="VIX",
        group="Global",
        section="Risk",
        display_name="VIX",
        frequency="D",
        source="FRED",
        unit="Index"
    ),

    "WORLD_TRADE": Indicator(
        code="WORLD_TRADE",
        group="Global",
        section="Trade",
        display_name="World Trade",
        frequency="M",
        source="CPB",
        unit="%"
    ),
}


def get_indicator(code):

    return INDICATORS[code]


def indicators_by_group(group):

    return [
        x
        for x in INDICATORS.values()
        if x.group == group
    ]


if __name__ == "__main__":

    print(f"{len(INDICATORS)} indicators loaded")