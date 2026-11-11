# ============================================================================
# File: macro_dashboard/test_dsge.py
# ============================================================================

from dsge.observables import validate_observables
from dsge.mappings import validate_mappings

validate_observables()
validate_mappings()

print("DSGE foundation OK")