# ============================================================================
# File: macro_dashboard/dashboard_value_loader.py
# ============================================================================

VALUES = {

    "GDP_FI": 1.7,
    "HICP_FI": 2.3,
    "UNRATE_FI": 7.1,

    "GDP_EA": 1.2,
    "HICP_EA": 2.0,

    "GDP_US": 2.5,
    "CPI_US": 2.7,
    "UNRATE_US": 4.2,

    "FI_10Y": 3.68,

    "BRENT": 82.5,
    "VIX": 18.4,
}


def get_value(code):

    return VALUES.get(code)
