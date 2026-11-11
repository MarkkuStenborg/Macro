# ============================================================================
# File: macro_dashboard/dsge/forecast_inputs.py
# Layer: DSGE
# Purpose: Build DSGE input vector from observable mappings
# ============================================================================

from dsge.mappings import MAPPINGS
from dsge.observables import OBSERVABLES


class ForecastInputs:

    def __init__(self):
        self.values = {}

    def set_value(self, observable: str, value: float):

        self.values[observable] = value

    def get_value(self, observable: str):

        return self.values.get(observable)

    def to_dict(self):

        return dict(self.values)


def create_demo_input():

    inputs = ForecastInputs()

    inputs.set_value("output_growth", 1.7)
    inputs.set_value("inflation", 2.3)
    inputs.set_value("labor_slack", 7.2)
    inputs.set_value("policy_rate", 2.25)
    inputs.set_value("oil_price_shock", 0.0)
    inputs.set_value("financial_stress", 0.0)

    return inputs


def validate_forecast_inputs():

    required = set()

    for observable in OBSERVABLES.values():
        required.add(observable.observable)

    return sorted(required)


if __name__ == "__main__":

    f = create_demo_input()

    print()
    print("Forecast Inputs")
    print("----------------")

    for key, value in f.to_dict().items():
        print(f"{key}: {value}")

    print()
    print("Required observables:")
    print(validate_forecast_inputs())
