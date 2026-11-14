"""Application settings plus shared financial and physical assumptions.

Every assumption needs a cited source (docs/PROJECT_PLAN.md section 4). Sources verified 2026-11-14.
NREL is now NLR (nrel.gov -> nlr.gov); NREL-era report titles are kept as published.
"""

import os
import tomllib
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, SecretStr

# Load API keys from the repo-root .env into os.environ on first import.
# Variables already set in the shell win (override=False), so tests and CI can set their own.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

rootPath = Path(__file__).resolve().parent


class Settings(BaseModel):
    dataMode: Literal["mock", "live"] = "mock"
    agentMode: Literal["mock", "live"] = "mock"
    costarSource: Literal["export", "api"] = "export"
    costarExportPath: Path = rootPath.parent / "CoStar Data Extract"
    modelName: str = "claude-sonnet-5-5"
    anthropicApiKey: SecretStr = SecretStr("")
    costarApiKey: SecretStr = SecretStr("")
    vexcelApiKey: SecretStr = SecretStr("")
    pvwattsApiKey: SecretStr = SecretStr("")
    geminiApiKey: SecretStr = SecretStr("")


def loadSettings() -> Settings:
    configValues = dict(dotenv_values(rootPath / ".env"))
    secretsPath = rootPath / ".streamlit" / "secrets.toml"

    if secretsPath.exists():
        with secretsPath.open("rb") as secretsFile:
            configValues.update(tomllib.load(secretsFile))

    for fieldName in Settings.model_fields:
        if fieldName in os.environ:
            configValues[fieldName] = os.environ[fieldName]

    knownValues = {
        fieldName: fieldValue
        for fieldName, fieldValue in configValues.items()
        if fieldName in Settings.model_fields and fieldValue is not None
    }
    settings = Settings(**knownValues)

    if not settings.costarExportPath.is_absolute():
        settings.costarExportPath = (rootPath / settings.costarExportPath).resolve()

    if settings.agentMode == "live" and not settings.anthropicApiKey.get_secret_value().strip():
        raise ValueError("Live agent mode requires anthropicApiKey.")

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

# Commercial rooftop PV installed price: modeled market price (MMP) $1.98/Wdc (MSP is $1.95/Wdc),
# 250 kWdc flat-roof school system, PV only, 2024 USD, before subsidies.
# Source: DOE, "Solar Photovoltaic System Cost Benchmarks", 2025Q1 PV-only benchmarks, Table 2.
# https://www.energy.gov/cmei/systems/solar-photovoltaic-system-cost-benchmarks
COST_PER_WATT_USD = 1.98

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
