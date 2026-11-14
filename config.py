"""All financial and physical assumptions live here. Every value needs a source (see docs/PROJECT_PLAN.md section 4)."""

USABLE_FACTOR = 0.6  # assumption: share of roof footprint usable for panels (tier 1)
POWER_DENSITY_KW_PER_M2 = None  # TODO: look up and cite
TILT_DEG = None  # TODO: look up and cite
PVWATTS_LOSSES_PCT = 14  # PVWatts default
ELECTRICITY_RATE_USD_PER_KWH = None  # TODO: EIA average commercial price, Texas
COST_PER_WATT_USD = None  # TODO: NREL or SEIA commercial benchmark
INCENTIVE_PCT = None  # TODO: verify current incentive rules
GRID_EF_KG_PER_KWH = None  # TODO: EPA eGRID, ERCOT (ERCT)
MIN_SYSTEM_KW = 50  # drop buildings below this size
