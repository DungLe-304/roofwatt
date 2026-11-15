"""Tool functions exposed to RoofWatt's model, including locally hosted Ollama models.

Each analysis tool takes only a buildingId and recomputes the chain below it (CoStar -> roof -> PVWatts ->
finance; PVWatts responses are cached), so the model never copies numbers between tools. Failures come back
as {"buildingId", "error"} so the agent can report them and continue with other buildings. Keep public tool
functions' docstrings specific: the model uses them to decide when and how to call each tool.
"""

import math
from concurrent.futures import ThreadPoolExecutor

import requests

import config
from data.costar_client import CostarClient
from data.costar_client import getBuilding as getBuildingData
from data.costar_client import searchBuildings as searchBuildingsData
from data.imagery import get_roof_image
from models.finance import compute_financials, cost_per_watt_for_size
from models.roof import estimate_roof
from models.solar import estimate_solar

toolErrors = (LookupError, ValueError, RuntimeError, requests.RequestException)


def _roof(building):
	return estimate_roof(building, usable_factor=config.USABLE_FACTOR)


def _solar(building):
	roof = _roof(building)
	if building.lat is None or building.lon is None:
		raise ValueError(f"{building.buildingId}: coordinates are missing, so PVWatts cannot run")
	systemKw = roof.usable_roof_m2 * config.POWER_DENSITY_KW_PER_M2
	solar = estimate_solar(building.buildingId, building.lat, building.lon, systemKw,
	                       tilt_deg=config.TILT_DEG, losses_pct=config.PVWATTS_LOSSES_PCT)
	return roof, solar


def _solarFields(roof, solar):
	return {
		"buildingId": solar.building_id,
		"usableRoofM2": roof.usable_roof_m2,
		"systemKw": solar.system_kw,
		"annualKwh": solar.annual_kwh,
		"belowMinimumSize": solar.system_kw < config.MIN_SYSTEM_KW,
	}


def _safe(buildingId, compute):
	try:
		return compute(getBuildingData(buildingId))
	except toolErrors as error:
		return {"buildingId": buildingId, "error": str(error)}


def analyzeRoof(buildingId: str) -> dict:
	"""Estimate the usable roof area (m²) of one building (tier 1: footprint × usable factor).

	Footprint is CoStar footprint if present, else the smaller of the typical floor area and gross building area / stories, converted ft² -> m².
	Returns usableRoofM2, method and the usable factor assumption, or an error.
	"""
	def compute(building):
		roof = _roof(building)
		return {"buildingId": roof.building_id, "usableRoofM2": roof.usable_roof_m2, "method": roof.method,
		        "assumptions": {"usableFactor": config.USABLE_FACTOR}}
	return _safe(buildingId, compute)


def estimateSolar(buildingId: str) -> dict:
	"""Size a rooftop PV system for one building and estimate its annual energy with NREL PVWatts v8.

	Returns usableRoofM2, systemKw, annualKwh, belowMinimumSize (system under the minimum size the
	ranking keeps) and the assumptions used, or an error.
	"""
	def compute(building):
		roof, solar = _solar(building)
		return _solarFields(roof, solar) | {"assumptions": {
			"powerDensityKwPerM2": config.POWER_DENSITY_KW_PER_M2, "tiltDeg": config.TILT_DEG,
			"lossesPct": config.PVWATTS_LOSSES_PCT, "minSystemKw": config.MIN_SYSTEM_KW}}
	return _safe(buildingId, compute)


def _financials(building) -> dict:
	roof, solar = _solar(building)
	costPerWatt = cost_per_watt_for_size(solar.system_kw, config.COST_PER_WATT_BY_SIZE_KW)
	finance = compute_financials(
		solar, rate_usd_per_kwh=config.ELECTRICITY_RATE_USD_PER_KWH, cost_per_watt_usd=costPerWatt,
		incentive_pct=config.INCENTIVE_PCT, grid_ef_kg_per_kwh=config.GRID_EF_KG_PER_KWH)
	payback = finance.simple_payback_yr
	return _solarFields(roof, solar) | {
		"annualSavingsUsd": finance.annual_savings_usd,
		"costPerWattUsd": costPerWatt,
		"capexUsd": finance.capex_usd,
		"netCapexUsd": finance.net_capex_usd,
		"simplePaybackYr": None if payback is None or math.isinf(payback) else payback,
		"co2TonsPerYear": finance.co2_tons_per_year,
	}


def _financeAssumptions() -> dict:
	return {
		"electricityRateUsdPerKwh": config.ELECTRICITY_RATE_USD_PER_KWH,
		"costPerWattUsd": "by system size (LBNL 2025 non-residential medians), see costPerWattUsd per building",
		"incentivePct": config.INCENTIVE_PCT,
		"gridEfKgPerKwh": config.GRID_EF_KG_PER_KWH,
	}


def computeFinancials(buildingId: str) -> dict:
	"""Annual savings, capex, net capex after the federal ITC, simple payback (years) and CO₂ avoided
	(t/yr) for one building. Runs the roof and solar steps itself.

	simplePaybackYr is null when the system produces no savings. Returns the assumptions used, or an error.
	"""
	def compute(building):
		result = _financials(building)
		return result | {"assumptions": _financeAssumptions() | {"costPerWattUsd": result["costPerWattUsd"]}}
	return _safe(buildingId, compute)


def _allMatches(city: str, propertyType: str, minSqft: float) -> list:
	return CostarClient().allBuildings(city, propertyType, minSqft)


def _analyze(building) -> dict:
	try:
		return _financials(building)
	except toolErrors as error:
		return {"buildingId": building.buildingId, "error": str(error)}


def rankBuildings(city: str, propertyType: str = "Office", minSqft: float = 0, limit: int = 10) -> dict:
	"""Analyze EVERY building matching the filters and return the top `limit` by solar payback.

	Use this for any "best / top N" request instead of calling computeFinancials building by building.
	Drops buildings with errors (reported in excluded.errors), systems below the minimum size and
	systems with no payback. Sorts by simplePaybackYr ascending (compared at 0.01-year precision), ties
	broken by co2TonsPerYear descending. Buildings with the same payback share a rank (1, 1, 1, 4, ...).
	Returns totalMatches, rankedCount, excluded, ranked rows and the assumptions used, or an error.
	"""
	try:
		buildings = _allMatches(city, propertyType, minSqft)
	except toolErrors as error:
		return {"error": str(error)}
	with ThreadPoolExecutor(max_workers=8) as pool:  # PVWatts calls are network-bound and cached
		results = list(pool.map(_analyze, buildings))

	errors, tooSmall, noPayback, rows = [], 0, 0, []
	for building, result in zip(buildings, results):
		if "error" in result:
			errors.append({"buildingId": result["buildingId"], "error": result["error"]})
		elif result["belowMinimumSize"]:
			tooSmall += 1
		elif result["simplePaybackYr"] is None:
			noPayback += 1
		else:
			result["simplePaybackYr"] = round(result["simplePaybackYr"], 2)
			rows.append({"address": building.address} | {key: value for key, value in result.items() if key != "belowMinimumSize"})
	rows.sort(key = lambda row: (row["simplePaybackYr"], -row["co2TonsPerYear"]))
	rows = [{"rank": index} | row for index, row in enumerate(rows, start = 1)]  # unique ranks 1, 2, 3, ...
	return {
		"city": city, "propertyType": propertyType, "totalMatches": len(buildings), "rankedCount": len(rows),
		"excluded": {"errors": errors, "belowMinimumSize": tooSmall, "noPayback": noPayback},
		"ranked": rows[:max(limit, 0)],
		"assumptions": _financeAssumptions() | {"usableFactor": config.USABLE_FACTOR, "minSystemKw": config.MIN_SYSTEM_KW},
	}


def getRoofImage(buildingId: str) -> dict:
	"""Fetch (or reuse from cache) a Vexcel aerial image centered on one building, for display in the UI.

	Returns imagePath (a local file path, not something to describe or analyze), or an error.
	"""
	def compute(building):
		if building.lat is None or building.lon is None:
			raise ValueError(f"{building.buildingId}: coordinates are missing, so no aerial image can be fetched")
		footprintM2 = _roof(building).usable_roof_m2 / config.USABLE_FACTOR
		extentM = max(80.0, 1.5 * math.sqrt(footprintM2))  # frame the whole roof plus margin (display choice)
		path = get_roof_image(building.buildingId, building.lat, building.lon, extent_m=extentM)
		return {"buildingId": building.buildingId, "imagePath": str(path)}
	return _safe(buildingId, compute)


roofWattTools = [searchBuildingsData, getBuildingData, analyzeRoof, estimateSolar, computeFinancials, rankBuildings, getRoofImage]