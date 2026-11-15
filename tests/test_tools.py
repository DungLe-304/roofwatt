"""Agent tool wrappers: CoStar lookup and PVWatts are faked; config values are the real sourced ones."""

import json

import pytest

import config
from agent import tools
from models.schemas import Building, SolarResult

KWH_PER_KW = 1400  # fake PVWatts yield for the tests


def make_building(**overrides):
	fields = dict(buildingId="42", propertyType="Office", address="1 Main St", lat=29.76, lon=-95.37,
	              buildingSqft=100_000, stories=4)
	fields.update(overrides)
	return Building(**fields)


@pytest.fixture
def fakes(monkeypatch):
	state = {"building": make_building(), "solarCalls": []}

	def fake_get_building(buildingId):
		if buildingId != state["building"].buildingId:
			raise LookupError(f"Building {buildingId} is absent from the CoStar extract.")
		return state["building"]

	def fake_estimate_solar(building_id, lat, lon, system_kw, *, tilt_deg, losses_pct):
		state["solarCalls"].append(dict(lat=lat, lon=lon, system_kw=system_kw, tilt_deg=tilt_deg, losses_pct=losses_pct))
		return SolarResult(building_id=building_id, system_kw=system_kw, annual_kwh=system_kw * KWH_PER_KW)

	monkeypatch.setattr(tools, "getBuildingData", fake_get_building)
	monkeypatch.setattr(tools, "estimate_solar", fake_estimate_solar)
	return state


def test_analyze_roof_uses_sqft_per_story_and_usable_factor(fakes):
	r = tools.analyzeRoof("42")
	assert r["buildingId"] == "42"
	assert r["usableRoofM2"] == pytest.approx(100_000 / 4 * 0.092903 * config.USABLE_FACTOR)
	assert r["method"] == "tier1_footprint_factor"


def test_estimate_solar_sizes_system_and_calls_pvwatts_with_config(fakes):
	r = tools.estimateSolar("42")
	roof_m2 = 100_000 / 4 * 0.092903 * config.USABLE_FACTOR
	assert r["systemKw"] == pytest.approx(roof_m2 * config.POWER_DENSITY_KW_PER_M2)
	assert r["annualKwh"] == pytest.approx(r["systemKw"] * KWH_PER_KW)
	call = fakes["solarCalls"][0]
	assert (call["lat"], call["lon"]) == (29.76, -95.37)
	assert call["tilt_deg"] == config.TILT_DEG
	assert call["losses_pct"] == config.PVWATTS_LOSSES_PCT


def test_compute_financials_uses_sourced_assumptions(fakes):
	r = tools.computeFinancials("42")
	# 100k ft² / 4 stories -> ~206 kW, in the LBNL 100-250 kW bin ($2.6/W)
	assert 100 < r["systemKw"] <= 250
	assert r["assumptions"]["costPerWattUsd"] == 2.6
	# payback = $/W * 1000 * (1 - ITC) / (kWh/kW * $/kWh)
	expected = 2.6 * 1000 * (1 - config.INCENTIVE_PCT) / (KWH_PER_KW * config.ELECTRICITY_RATE_USD_PER_KWH)
	assert r["simplePaybackYr"] == pytest.approx(expected)
	assert r["co2TonsPerYear"] == pytest.approx(r["annualKwh"] * config.GRID_EF_KG_PER_KWH / 1000)
	assert r["systemKw"] > 0
	assert r["assumptions"]["incentivePct"] == config.INCENTIVE_PCT


def test_zero_energy_payback_is_null_and_valid_json(fakes, monkeypatch):
	monkeypatch.setattr(tools, "estimate_solar",
	                    lambda building_id, lat, lon, system_kw, **kw: SolarResult(building_id=building_id, system_kw=system_kw, annual_kwh=0))
	r = tools.computeFinancials("42")
	assert r["simplePaybackYr"] is None
	json.dumps(r, allow_nan=False)


@pytest.mark.parametrize("tool", [tools.analyzeRoof, tools.estimateSolar, tools.computeFinancials])
def test_unknown_building_returns_error(fakes, tool):
	r = tool("missing")
	assert r["buildingId"] == "missing"
	assert "absent" in r["error"]


def test_missing_size_returns_error(fakes):
	fakes["building"] = make_building(stories=None)
	r = tools.computeFinancials("42")
	assert "building_sqft + stories" in r["error"]


def test_missing_coordinates_returns_error_without_calling_pvwatts(fakes):
	fakes["building"] = make_building(lat=None)
	r = tools.estimateSolar("42")
	assert "coordinates" in r["error"]
	assert fakes["solarCalls"] == []


def test_all_tools_are_registered():
	names = {t.__name__ for t in tools.roofWattTools}
	assert {"searchBuildings", "getBuilding", "analyzeRoof", "estimateSolar", "computeFinancials", "rankBuildings"} <= names


@pytest.fixture
def city(monkeypatch):
	"""Five matches. C (~617 kW) is in a cheaper $/W bin, so it pays back fastest despite lower yield.
	A (~206 kW) and B (~247 kW) share the 100-250 kW bin and yield, so they tie; B avoids more CO2.
	D is too small, E has no stories."""
	yields = {"A": 1500, "B": 1500, "C": 1400, "D": 1500}
	buildings = [
		make_building(buildingId="A", buildingSqft=100_000),
		make_building(buildingId="C", buildingSqft=300_000),
		make_building(buildingId="B", buildingSqft=120_000),
		make_building(buildingId="D", buildingSqft=4_000),
		make_building(buildingId="E", stories=None),
	]
	seen = {}

	def fake_all_matches(cityName, propertyType, minSqft):
		seen.update(city=cityName, propertyType=propertyType, minSqft=minSqft)
		return buildings

	def fake_estimate_solar(building_id, lat, lon, system_kw, *, tilt_deg, losses_pct):
		return SolarResult(building_id=building_id, system_kw=system_kw, annual_kwh=system_kw * yields[building_id])

	monkeypatch.setattr(tools, "_allMatches", fake_all_matches)
	monkeypatch.setattr(tools, "estimate_solar", fake_estimate_solar)
	return seen


def test_rank_sorts_by_payback_then_co2_and_every_rank_is_unique(city):
	r = tools.rankBuildings("Houston", "Office", limit=10)
	assert [(row["rank"], row["buildingId"]) for row in r["ranked"]] == [(1, "C"), (2, "B"), (3, "A")]
	assert r["ranked"][1]["simplePaybackYr"] == r["ranked"][2]["simplePaybackYr"]
	assert r["ranked"][1]["co2TonsPerYear"] > r["ranked"][2]["co2TonsPerYear"]
	assert r["ranked"][0]["costPerWattUsd"] == 2.1
	assert city == {"city": "Houston", "propertyType": "Office", "minSqft": 0}


def test_rank_reports_what_it_screened_and_excluded(city):
	r = tools.rankBuildings("Houston")
	assert r["totalMatches"] == 5
	assert r["rankedCount"] == 3
	assert r["excluded"]["belowMinimumSize"] == 1
	assert r["excluded"]["errors"] == [{"buildingId": "E", "error": r["excluded"]["errors"][0]["error"]}]
	assert "building_sqft + stories" in r["excluded"]["errors"][0]["error"]
	json.dumps(r, allow_nan=False)


def test_rank_respects_limit(city):
	r = tools.rankBuildings("Houston", limit=2)
	assert [row["buildingId"] for row in r["ranked"]] == ["C", "B"]
	assert r["rankedCount"] == 3


def test_rank_unsupported_city_returns_error(monkeypatch):
	def boom(cityName, propertyType, minSqft):
		raise ValueError("Supported cities: Houston and Los Angeles.")
	monkeypatch.setattr(tools, "_allMatches", boom)
	assert "Supported cities" in tools.rankBuildings("Boston")["error"]


def test_get_roof_image_returns_path_or_error(fakes, monkeypatch, tmp_path):
	image = tmp_path / "42.jpeg"
	calls = []

	def fake_image(building_id, lat, lon, *, extent_m):
		calls.append(extent_m)
		return image
	monkeypatch.setattr(tools, "get_roof_image", fake_image)
	assert tools.getRoofImage("42") == {"buildingId": "42", "imagePath": str(image)}
	# footprint 100k ft² / 4 stories = ~2,323 m² -> side ~48 m; frame = 1.5x side, at least the 80 m minimum
	assert calls == [80]
	fakes["building"] = make_building(buildingSqft=400_000, stories=1)  # ~37,161 m² -> side ~193 m -> ~289 m
	tools.getRoofImage("42")
	assert calls[-1] == pytest.approx(1.5 * (400_000 * 0.092903) ** 0.5, abs=1)

	def rejected(building_id, lat, lon, *, extent_m):
		raise RuntimeError("Vexcel rejected VEXCEL_API_KEY (HTTP 401)")
	monkeypatch.setattr(tools, "get_roof_image", rejected)
	assert "401" in tools.getRoofImage("42")["error"]
	fakes["building"] = make_building(lat=None)
	assert "coordinates" in tools.getRoofImage("42")["error"]
