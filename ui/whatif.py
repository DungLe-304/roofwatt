"""What-if recalculation of ranked rows when the user changes assumptions in the sidebar (UI only).

Uses the same pure functions as the tools (models.finance). A different usable factor scales usable roof, system
size and annual energy proportionally: PVWatts AC output is linear in system size at a fixed DC/AC ratio
(checked 2026-11-14: 350 kW vs 100 kW at the same Houston site -> exactly 3.5x the kWh), so no new API call is needed.
Only the rows already shown are recalculated; a full re-rank of every building needs a new agent run.
"""

import config
from models.finance import compute_financials, cost_per_watt_for_size
from models.schemas import SolarResult


def defaultAssumptions() -> dict:
	"""The sourced values from config.py; flatCostPerWatt None means the size-based LBNL medians."""
	return {"ratePerKwh": config.ELECTRICITY_RATE_USD_PER_KWH, "flatCostPerWatt": None,
		"incentivePct": config.INCENTIVE_PCT, "usableFactor": config.USABLE_FACTOR}


def isDefault(assumptions: dict | None) -> bool:
	return assumptions is None or assumptions == defaultAssumptions()


def recalculate(rows: list[dict], assumptions: dict, baseUsableFactor: float = config.USABLE_FACTOR) -> list[dict]:
	"""Rows recomputed with `assumptions`, re-ranked among themselves (payback asc, CO₂ desc, ties share a rank)."""
	scale = assumptions["usableFactor"] / baseUsableFactor
	updated = []
	for row in rows:
		systemKw, annualKwh = row["systemKw"] * scale, row["annualKwh"] * scale
		costPerWatt = assumptions["flatCostPerWatt"] or cost_per_watt_for_size(systemKw, config.COST_PER_WATT_BY_SIZE_KW)
		finance = compute_financials(SolarResult(buildingId=str(row["buildingId"]), systemKw=systemKw, annualKwh=annualKwh),
			rate_usd_per_kwh=assumptions["ratePerKwh"], cost_per_watt_usd=costPerWatt,
			incentive_pct=assumptions["incentivePct"], grid_ef_kg_per_kwh=config.GRID_EF_KG_PER_KWH)
		updated.append(row | {
			"usableRoofM2": row["usableRoofM2"] * scale, "systemKw": systemKw, "annualKwh": annualKwh,
			"costPerWattUsd": costPerWatt, "annualSavingsUsd": finance.annual_savings_usd, "capexUsd": finance.capex_usd,
			"netCapexUsd": finance.net_capex_usd, "simplePaybackYr": round(finance.simple_payback_yr, 2),
			"co2TonsPerYear": finance.co2_tons_per_year, "belowMinimumSize": systemKw < config.MIN_SYSTEM_KW,
		})
	updated.sort(key=lambda row: (row["simplePaybackYr"], -row["co2TonsPerYear"]))
	for index, row in enumerate(updated, start=1):
		row["rank"] = index  # unique ranks; equal payback is ordered by CO₂ avoided
	return updated
