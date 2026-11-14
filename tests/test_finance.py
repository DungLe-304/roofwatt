"""Hand-computed finance cases. Inputs are explicit test values, not sourced assumptions."""

import math

import pytest

from models.finance import compute_financials
from models.schemas import SolarResult


def test_typical_system_with_incentive():
    # savings = 150_000 * 0.10 = 15_000; capex = 100 kW * 1000 W/kW * $2.00 = 200_000
    # net = 200_000 * (1 - 0.30) = 140_000; payback = 140_000 / 15_000 = 9.333 yr
    # co2 = 150_000 kWh * 0.4 kg/kWh / 1000 = 60 t
    solar = SolarResult(building_id="b1", system_kw=100, annual_kwh=150_000)
    r = compute_financials(solar, rate_usd_per_kwh=0.10, cost_per_watt_usd=2.0,
                           incentive_pct=0.30, grid_ef_kg_per_kwh=0.4)
    assert r.building_id == "b1"
    assert r.annual_savings_usd == pytest.approx(15_000)
    assert r.capex_usd == pytest.approx(200_000)
    assert r.net_capex_usd == pytest.approx(140_000)
    assert r.simple_payback_yr == pytest.approx(140_000 / 15_000)
    assert r.co2_tons_per_year == pytest.approx(60)


def test_no_incentive_net_equals_capex():
    # capex = 250 * 1000 * 1.6 = 400_000; savings = 362_500 * 0.08 = 29_000
    # payback = 400_000 / 29_000 = 13.793 yr; co2 = 362_500 * 0.37 / 1000 = 134.125 t
    solar = SolarResult(building_id="b2", system_kw=250, annual_kwh=362_500)
    r = compute_financials(solar, rate_usd_per_kwh=0.08, cost_per_watt_usd=1.6,
                           incentive_pct=0.0, grid_ef_kg_per_kwh=0.37)
    assert r.capex_usd == pytest.approx(400_000)
    assert r.net_capex_usd == pytest.approx(r.capex_usd)
    assert r.simple_payback_yr == pytest.approx(13.7931, rel=1e-4)
    assert r.co2_tons_per_year == pytest.approx(134.125)


def test_zero_energy_gives_infinite_payback():
    solar = SolarResult(building_id="b3", system_kw=60, annual_kwh=0)
    r = compute_financials(solar, rate_usd_per_kwh=0.10, cost_per_watt_usd=2.0,
                           incentive_pct=0.30, grid_ef_kg_per_kwh=0.4)
    assert math.isinf(r.simple_payback_yr)
    assert r.co2_tons_per_year == 0
