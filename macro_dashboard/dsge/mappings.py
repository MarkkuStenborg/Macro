# ============================================================================
# File: macro_dashboard/dsge/mappings.py
# ============================================================================

from dsge.observables import OBSERVABLES


MAPPINGS = {
    "GDP_FI": "output_growth",
    "GDP_EA": "output_growth",
    "GDP_US": "output_growth",

    "HICP_FI": "inflation",
    "HICP_EA": "inflation",
    "CPI_US": "inflation",

    "UNRATE_FI": "labor_slack",
    "UNRATE_EA": "labor_slack",
    "UNRATE_US": "labor_slack",

    "ECB_RATE": "policy_rate",
    "FEDFUNDS": "policy_rate",

    "BRENT": "oil_price_shock",
    "VIX": "financial_stress",

    "WORLD_TRADE": "external_demand"
}


def validate_mappings():

    for series in MAPPINGS:

        if series not in OBSERVABLES:

            raise ValueError(
                f"Missing observable: {series}"
            )

    return True


if __name__ == "__main__":

    validate_mappings()

    print("Mappings OK")