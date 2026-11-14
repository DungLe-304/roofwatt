"""Hand-computed tier-1 roof cases. Inputs are explicit test values, not sourced assumptions."""

import pytest

from models.roof import estimate_roof
from models.schemas import Building


def make_building(**overrides) -> Building:
    fields = dict(
        building_id="b1", address="1 Main St, Houston, TX", lat=29.76, lon=-95.37,
        property_type="Office", building_sqft=None, footprint_m2=None, stories=None,
        year_built=None, owner_name=None,
    )
    fields.update(overrides)
    return Building(**fields)


def test_uses_footprint_when_present():
    # 2_000 m² * 0.6 = 1_200 m²; sqft/stories are ignored when footprint exists
    b = make_building(footprint_m2=2_000, building_sqft=999_999, stories=1)
    r = estimate_roof(b, usable_factor=0.6)
    assert r.building_id == "b1"
    assert r.usable_roof_m2 == pytest.approx(1_200)
    assert r.method == "tier1_footprint_factor"
    assert r.image_path is None


def test_falls_back_to_sqft_per_story_in_m2():
    # 100_000 ft² / 4 stories = 25_000 ft² * 0.092903 = 2_322.575 m²; * 0.5 = 1_161.2875 m²
    b = make_building(building_sqft=100_000, stories=4)
    r = estimate_roof(b, usable_factor=0.5)
    assert r.usable_roof_m2 == pytest.approx(1_161.2875)
    assert r.method == "tier1_footprint_factor"


@pytest.mark.parametrize("sqft, stories", [(None, 3), (50_000, None), (50_000, 0), (None, None)])
def test_missing_size_data_raises(sqft, stories):
    b = make_building(building_sqft=sqft, stories=stories)
    with pytest.raises(ValueError, match="b1"):
        estimate_roof(b, usable_factor=0.6)
