"""Savings, payback and CO2 (pure functions; formulas in docs/PROJECT_PLAN.md section 4).

Assumption values are passed in explicitly; callers take them from config.py.
"""

import math

from models.schemas import FinanceResult, SolarResult


def cost_per_watt_for_size(system_kw: float, bins) -> float:
    """Installed $/W for a system size. bins: ((upper_kw_inclusive, usd_per_w), ...) ascending, last upper = inf."""
    for upper_kw, usd_per_w in bins:
        if system_kw <= upper_kw:
            return usd_per_w
    raise ValueError(f"no cost bin covers {system_kw} kW")


def compute_financials(
    solar: SolarResult,
    *,
    rate_usd_per_kwh: float,
    cost_per_watt_usd: float,
    incentive_pct: float,
    grid_ef_kg_per_kwh: float,
) -> FinanceResult:
    annual_savings_usd = solar.annual_kwh * rate_usd_per_kwh
    capex_usd = solar.system_kw * 1000 * cost_per_watt_usd  # kW -> W
    net_capex_usd = capex_usd * (1 - incentive_pct)
    payback = net_capex_usd / annual_savings_usd if annual_savings_usd > 0 else math.inf
    return FinanceResult(
        building_id=solar.building_id,
        annual_savings_usd=annual_savings_usd,
        capex_usd=capex_usd,
        net_capex_usd=net_capex_usd,
        simple_payback_yr=payback,
        co2_tons_per_year=solar.annual_kwh * grid_ef_kg_per_kwh / 1000,  # kg -> t
    )
