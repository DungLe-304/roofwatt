"""What-if recalculation: sourced defaults reproduce the tool's numbers; changed assumptions follow the formulas."""

import pytest

import config
from ui.whatif import defaultAssumptions, isDefault, recalculate

ROWS = [
	{"rank": 1, "address": "A", "buildingId": "1", "usableRoofM2": 7906.04, "systemKw": 1167.72, "annualKwh": 1660572.5,
		"annualSavingsUsd": 142145.01, "costPerWattUsd": 1.9, "capexUsd": 2218672.19, "netCapexUsd": 1553070.53,
		"simplePaybackYr": 10.93, "co2TonsPerYear": 552.76},
	{"rank": 2, "address": "B", "buildingId": "2", "usableRoofM2": 1000.0, "systemKw": 147.7, "annualKwh": 207000.0,
		"annualSavingsUsd": 17719.2, "costPerWattUsd": 2.6, "capexUsd": 384020.0, "netCapexUsd": 268814.0,
		"simplePaybackYr": 15.17, "co2TonsPerYear": 68.91},
]


def test_sourced_defaults_reproduce_the_tool_rows():
	for before, after in zip(ROWS, recalculate(ROWS, defaultAssumptions())):
		for field in ("systemKw", "annualKwh", "annualSavingsUsd", "capexUsd", "netCapexUsd", "co2TonsPerYear"):
			assert after[field] == pytest.approx(before[field], rel=1e-3), field
		assert after["simplePaybackYr"] == pytest.approx(before["simplePaybackYr"], abs=0.01)
		assert after["rank"] == before["rank"]
	assert isDefault(None) and isDefault(defaultAssumptions())


def test_rate_and_incentive_change_savings_and_net_cost_only():
	row = recalculate(ROWS[:1], defaultAssumptions() | {"ratePerKwh": 0.12, "incentivePct": 0.0})[0]
	assert row["annualSavingsUsd"] == pytest.approx(1660572.5 * 0.12)
	assert row["netCapexUsd"] == pytest.approx(row["capexUsd"])
	assert row["systemKw"] == pytest.approx(1167.72)
	assert row["simplePaybackYr"] == round(row["capexUsd"] / row["annualSavingsUsd"], 2)


def test_usable_factor_scales_size_and_energy_and_rebins_the_price():
	half = config.USABLE_FACTOR / 2
	row = recalculate(ROWS[1:], defaultAssumptions() | {"usableFactor": half})[0]
	assert row["systemKw"] == pytest.approx(147.7 / 2) and row["annualKwh"] == pytest.approx(207000 / 2)
	assert row["costPerWattUsd"] == 2.8  # 73.85 kW falls in the 50-100 kW bin
	assert row["belowMinimumSize"] is False
	tiny = recalculate(ROWS[1:], defaultAssumptions() | {"usableFactor": config.USABLE_FACTOR / 4})[0]
	assert tiny["belowMinimumSize"] is True  # 36.9 kW < MIN_SYSTEM_KW


def test_flat_price_overrides_the_size_bins_and_rows_are_re_ranked():
	rows = recalculate(ROWS, defaultAssumptions() | {"flatCostPerWatt": 1.0})
	assert {row["costPerWattUsd"] for row in rows} == {1.0}
	assert [row["rank"] for row in rows] == [1, 2]
	assert rows[0]["simplePaybackYr"] <= rows[1]["simplePaybackYr"]


def test_equal_payback_still_gets_unique_ranks():
	twin = ROWS[0] | {"rank": 1, "buildingId": "3", "usableRoofM2": ROWS[0]["usableRoofM2"] / 2,
		"systemKw": ROWS[0]["systemKw"] / 2, "annualKwh": ROWS[0]["annualKwh"] / 2}  # same price bin, same payback
	rows = recalculate([ROWS[0], twin], defaultAssumptions() | {"flatCostPerWatt": 1.0})
	assert rows[0]["simplePaybackYr"] == rows[1]["simplePaybackYr"]
	assert [(row["rank"], row["buildingId"]) for row in rows] == [(1, "1"), (2, "3")]  # more CO₂ ranks first
