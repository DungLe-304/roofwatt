"""Usable roof area, tier 1: footprint × usable factor (docs/PROJECT_PLAN.md section 4).

The usable factor is passed in explicitly; callers take it from config.USABLE_FACTOR.
"""

from models.schemas import Building, RoofResult

M2_PER_FT2 = 0.092903  # unit conversion, exact to 6 digits (1 ft = 0.3048 m)


def _footprint_m2(building: Building) -> float:
    if building.footprint_m2 is not None:
        return building.footprint_m2
    if building.building_sqft is not None and building.stories:
        return building.building_sqft / building.stories * M2_PER_FT2
    raise ValueError(
        f"{building.building_id}: no footprint_m2 and no building_sqft + stories (>0) to derive it"
    )


def estimate_roof(building: Building, *, usable_factor: float) -> RoofResult:
    return RoofResult(
        building_id=building.building_id,
        usable_roof_m2=_footprint_m2(building) * usable_factor,
        method="tier1_footprint_factor",
        image_path=None,
    )
