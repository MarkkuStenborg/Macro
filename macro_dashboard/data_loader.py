# ============================================================================
# File: macro_dashboard/dsge/data_loader.py
# Layer: DSGE
# Purpose: Build DSGE observation vector from observables
# ============================================================================

from pathlib import Path

from dsge.observables import OBSERVABLES
from dsge.mappings import MAPPINGS


ROOT = Path(__file__).resolve().parent.parent

STORE_DIR = ROOT / "store"


class DSGEObservationVector:

    def __init__(self):

        self.values = {}

    def add(self, observable, value):

        self.values[observable] = value

    def get(self, observable):

        return self.values.get(observable)

    def as_dict(self):

        return dict(self.values)

    def __repr__(self):

        return str(self.values)


def build_observation_vector():

    vector = DSGEObservationVector()

    #
    # Placeholder values.
    #
    # Later these come from store/raw,
    # normalized data or model_inputs.
    #

    vector.add("output_growth", None)
    vector.add("inflation", None)
    vector.add("labor_slack", None)
    vector.add("policy_rate", None)
    vector.add("oil_price_shock", None)
    vector.add("financial_stress", None)
    vector.add("external_demand", None)
    vector.add("china_activity", None)
    vector.add("china_inflation", None)

    return vector


def validate_structure():

    missing = []

    observables = {
        obs.observable
        for obs in OBSERVABLES.values()
    }

    for observable in observables:

        found = False

        for mapping in MAPPINGS.values():

            if mapping == observable:
                found = True
                break

        if not found:
            missing.append(observable)

    return missing


if __name__ == "__main__":

    vector = build_observation_vector()

    print()
    print("DSGE Observation Vector")
    print("-----------------------")

    for key, value in vector.as_dict().items():
        print(f"{key}: {value}")

    print()

    missing = validate_structure()

    if missing:

        print("Missing mappings:")
        print(missing)

    else:

        print("All observables mapped.")
