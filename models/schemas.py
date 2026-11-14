"""Data contracts shared by tools, models and UI (see docs/PROJECT_PLAN.md section 3)."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Building:
    building_id: str
    address: str
    lat: float
    lon: float
    property_type: str
    building_sqft: Optional[float]
    footprint_m2: Optional[float]  # if CoStar lacks it: building_sqft / stories, converted to m²
    stories: Optional[int]
    year_built: Optional[int]
    owner_name: Optional[str]


@dataclass
class RoofResult:
    building_id: str
    usable_roof_m2: float
    method: str  # "tier1_footprint_factor" | "tier2_sam"
    image_path: Optional[str]


@dataclass
class SolarResult:
    building_id: str
    system_kw: float
    annual_kwh: float


@dataclass
class FinanceResult:
    building_id: str
    annual_savings_usd: float
    capex_usd: float
    net_capex_usd: float
    simple_payback_yr: float
    co2_tons_per_year: float
