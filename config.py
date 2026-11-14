"""Application settings plus shared financial and physical assumptions.

Every assumption needs a cited source (docs/PROJECT_PLAN.md section 4). Sources verified 2026-11-14.
NREL is now NLR (nrel.gov -> nlr.gov); NREL-era report titles are kept as published.
"""

import os
import tomllib
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values as dotenvValues
from dotenv import load_dotenv
from pydantic import BaseModel

rootPath = Path(__file__).resolve().parent  # repo root (config.py lives there)

# Load API keys from the repo-root .env into os.environ on first import (models/solar.py reads NLR_API_KEY).
# Variables already set in the shell win (override=False), so tests and CI can set their own.
load_dotenv(rootPath / ".env", override=False)

class Settings(BaseModel):
	"""App settings, overridable from .env / .streamlit/secrets.toml / environment by field name.

	API keys are not stored here: modules read them from their env names (NLR_API_KEY, GOOGLE_API_KEY, VEXCEL_API_KEY).
	"""
	agentMode: Literal["mock", "live"] = "mock"
	modelName: str = "google_genai:gemini-4-hydrogen"  # LangChain id; langchain-google-genai reads GOOGLE_API_KEY
	agentContextMessages: int = 6
	agentContextCharacters: int = 10000
	agentMaxOutputTokens: int = 1200
	agentMaxRetries: int = 2

def loadSettings() -> Settings:
	configValues = dict(dotenvValues(rootPath / ".env"))
	secretsPath = rootPath / ".streamlit" / "secrets.toml"

	if secretsPath.exists():
		with secretsPath.open("rb") as secretsFile:
			configValues.update(tomllib.load(secretsFile))

	for fieldName in Settings.model_fields:
		if fieldName in os.environ:
			configValues[fieldName] = os.environ[fieldName]

	knownValues = {fieldName: fieldValue for fieldName, fieldValue in configValues.items() if fieldName in Settings.model_fields and fieldValue is not None}
	settings = Settings(**knownValues)

	googleApiKey = os.environ.get("GOOGLE_API_KEY") or configValues.get("GOOGLE_API_KEY") or ""
	if settings.agentMode == "live" and not googleApiKey.strip():
		raise ValueError("Live agent mode requires GOOGLE_API_KEY (Gemini).")

	return settings

# --- Roof -------------------------------------------------------------------------------------
# Assumption (unsourced): share of the roof footprint free of setbacks/HVAC/obstructions. Tier 1 only;
# replaced by SAM segmentation in tier 2. Label as an assumption in the UI (plan §4).
USABLE_FACTOR = 0.6

# --- System size ------------------------------------------------------------------------------
# Module STC power per m² of module: 500 W module at 21.1% efficiency -> 0.211 kW/m² (at 1 kW/m² STC).
# Source: DOE, "Solar Photovoltaic System Cost Benchmarks", 2025Q1 commercial (CPV) system:
# "Each module has a rated power of 500 watts, corresponding to an efficiency of 21.1%."
# https://www.energy.gov/cmei/systems/solar-photovoltaic-system-cost-benchmarks
MODULE_POWER_DENSITY_KW_PER_M2 = 0.211
# Module area / roof area on flat roofs (row spacing for tilted racks): 0.70.
# Source: Gagnon et al. 2016, "Rooftop Solar Photovoltaic Technical Potential in the United States",
# NREL/TP-6A20-65298, Table 1 (p. 13): "Ratio of module area to roof area 0.70" (flat roofs).
# https://docs.nlr.gov/docs/fy16osti/65298.pdf
FLAT_ROOF_MODULE_TO_ROOF_RATIO = 0.70
# kW of PV per m² of usable roof = 0.211 * 0.70 = 0.1477
POWER_DENSITY_KW_PER_M2 = MODULE_POWER_DENSITY_KW_PER_M2 * FLAT_ROOF_MODULE_TO_ROOF_RATIO

# --- PVWatts inputs ---------------------------------------------------------------------------
# Flat-roof module tilt, south-facing. Source: Gagnon et al. 2016, Table 1 (p. 13): "Tilt 15 degrees"
# (flat roofs), "Azimuth 180 degrees (south facing)".
TILT_DEG = 15
PVWATTS_LOSSES_PCT = 14  # PVWatts default system losses (Gagnon et al. 2016 Table 1 uses 14.08%)

# --- Finance ----------------------------------------------------------------------------------
# Texas commercial average retail price, full-year 2025 (final): 8.56 cents/kWh.
# Source: EIA, Electric Power Annual, Table 2.10 (2025 and 2024).
# https://www.eia.gov/electricity/annual/html/epa_02_10.html
# Caveat: an all-in average (includes demand charges); solar mostly offsets energy charges.
ELECTRICITY_RATE_USD_PER_KWH = 0.0856

# Installed price by system size: median up-front price, U.S. non-residential PV installed in 2025, 2025$/W_DC,
# before incentives (national medians; Texas not broken out). Each entry: (upper bound kW, inclusive; $/W).
# Source: LBNL, "U.S. Distributed Solar and Storage 2026 Data Update" (Aug 2026), slide 36 "Economies of Scale
# with PV System Size", chart "Non-Residential Systems Installed in 2025", labeled medians.
# https://emp.lbl.gov/sites/default/files/2026-08/Distributed%20Solar%20&%20Storage-2026%20Data%20Update_FINAL.pdf
# Replaces the single DOE 2025Q1 benchmark ($1.98/W for a 250 kW school roof), which made payback flat across sizes.
COST_PER_WATT_BY_SIZE_KW = (
    (10, 3.6), (20, 3.1), (50, 3.0), (100, 2.8),  # small non-residential
    (250, 2.6), (500, 2.3), (1000, 2.1), (float("inf"), 1.9),  # large non-residential (> 100 kW)
)

# Federal clean electricity ITC, IRC §48E(a)(2)(A)(ii): 30% for a facility under 1 MW AC, or larger
# facilities meeting prevailing wage + apprenticeship (§48E(d)(3)-(4)). Bonus adders (domestic content,
# energy community) are not included.
# Caveat: under Pub. L. 119-21 (OBBBA) §70513, solar facilities that begin construction after
# 2026-07-04 get no credit unless placed in service by 2027-12-31 (§48E(e)(4)). Texas has no state ITC.
# Sources: https://www.law.cornell.edu/uscode/text/26/48E
#          https://www.irs.gov/credits-deductions/clean-electricity-investment-credit
INCENTIVE_PCT = 0.30

# ERCOT (eGRID subregion ERCT) CO2 total output emission rate: 733.862 lb/MWh.
# Source: EPA eGRID2023 (2023 data, Revision 2, released 2025-06-12), "eGRID Subregion Total Output
# Emission Rates". Latest edition as of 2026-11-14. https://www.epa.gov/egrid/summary-data
# Note: total output rate, not the (higher) non-baseload/marginal rate.
GRID_EF_LB_PER_MWH = 733.862
KG_PER_LB = 0.45359237  # exact by definition
GRID_EF_KG_PER_KWH = GRID_EF_LB_PER_MWH * KG_PER_LB / 1000  # lb/MWh -> kg/kWh = 0.3329

# --- Ranking ----------------------------------------------------------------------------------
MIN_SYSTEM_KW = 50  # drop buildings below this size (project rule, plan §4)

# --- Short citations for the UI (full references in the comments above) ----------------------------
SOURCES = {
    "USABLE_FACTOR": "Assumption (unsourced)",
    "POWER_DENSITY_KW_PER_M2": "DOE PV Cost Benchmarks 2025Q1 (0.211 kW/m² module) × Gagnon et al. 2016, NREL Table 1 "
                               "(0.70 module/roof)",
    "PVWATTS": "NREL PVWatts v8 (tilt and azimuth: Gagnon et al. 2016, NREL Table 1)",
    "ELECTRICITY_RATE_USD_PER_KWH": "EIA Electric Power Annual, Table 2.10 (Texas commercial, 2025)",
    "COST_PER_WATT_BY_SIZE_KW": "LBNL Distributed Solar & Storage 2026 Data Update, slide 36 (2025 non-res. medians)",
    "INCENTIVE_PCT": "IRC §48E ITC; requires placed in service by 2027-12-31 (Pub. L. 119-21 §70513)",
    "GRID_EF_KG_PER_KWH": "EPA eGRID2023, ERCOT (ERCT) total output rate",
    "BUILDING": "CoStar extract (gross building area, stories)",
}
