"""Usable roof area, tier 1: footprint × usable factor (docs/PROJECT_PLAN.md section 4).

The usable factor is passed in explicitly; callers take it from config.USABLE_FACTOR.

CoStar has no measured roof footprint, so it is estimated from floor plates: the smaller of CoStar's typical
floor (grossTypicalFloorSquareFeet) and gross area ÷ stories. Gross ÷ stories alone overstates towers with a
podium or a large lower floor (1840 Dynamic Way: 70,000 ft² per story vs a 35,000 ft² typical floor, and the
Vexcel roof image measures about 3,400 m², i.e. the typical floor).
"""

from models.schemas import Building, RoofResult

M2_PER_FT2 = 0.092903  # unit conversion, exact to 6 digits (1 ft = 0.3048 m)
MIN_TYPICAL_FLOOR_SHARE = 0.25  # data sanity check (not a sourced assumption): a typical floor under 25% of
# gross ÷ stories is treated as a CoStar entry error (352552: 2 ft² typical floor in a 106,176 ft² building)


def footprint_sqft(building: Building) -> float:
    """Estimated roof footprint in ft² (smaller of typical floor and gross ÷ stories)."""
    perStory = building.building_sqft / building.stories if building.building_sqft and building.stories else None
    typical = building.typical_floor_sqft
    if typical and perStory and typical < MIN_TYPICAL_FLOOR_SHARE * perStory:
        typical = None
    plates = [plate for plate in (typical, perStory) if plate]
    if not plates:
        raise ValueError(
            f"{building.building_id}: no footprint_m2, typical floor area or building_sqft + stories (>0) to derive it"
        )
    return min(plates)


def _footprint_m2(building: Building) -> float:
    if building.footprint_m2 is not None:
        return building.footprint_m2
    return footprint_sqft(building) * M2_PER_FT2


def estimate_roof(building: Building, *, usable_factor: float) -> RoofResult:
    return RoofResult(
        building_id=building.building_id,
        usable_roof_m2=_footprint_m2(building) * usable_factor,
        method="tier1_footprint_factor",
        image_path=None,
    )
