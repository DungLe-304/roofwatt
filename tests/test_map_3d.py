"""Offline checks for sourced geometry, local query dates and the flat map."""

import json

from data.buildings import buildingPolygons
from ui.ranking import rankingDeck
from ui.sunlight import queryDateFor


def test_geometry_keeps_missing_heights_flat():
	geometry = [{"lon": -95.4, "lat": 29.7}, {"lon": -95.399, "lat": 29.7}, {"lon": -95.4, "lat": 29.701}, {"lon": -95.4, "lat": 29.7}]
	rows = buildingPolygons({"elements": [{"id": 1, "geometry": geometry, "tags": {"height": "20 m"}}, {"id": 2, "geometry": geometry, "tags": {"building:levels": "3"}}]})
	assert [row["heightM"] for row in rows] == [20, 0]
	assert "Unknown" in rows[1]["heightLabel"]
	assert buildingPolygons({"elements": [{"id": 3, "geometry": geometry[:-1]}]}) == []


def test_query_date_uses_city_timezone_at_submission():
	assert queryDateFor("Houston", "2026-11-15T07:00:00+00:00") == "2026-11-15"
	assert queryDateFor("Los Angeles", "2026-11-15T07:00:00+00:00") == "2026-11-14"


def test_map_serializes_flat_footprints_for_focus():
	row = {"rank": 1, "buildingId": "1", "lat": 29.7, "lon": -95.4, "simplePaybackYr": 12, "annualSavingsUsd": 10000, "co2TonsPerYear": 20, "systemKw": 100}
	buildings = [{"footprint": [[-95.4, 29.7], [-95.399, 29.7], [-95.4, 29.701], [-95.4, 29.7]], "heightM": 20}]
	spec = json.loads(rankingDeck([row], buildings = buildings, focusRow = row).to_json())
	assert spec["initialViewState"]["pitch"] == 0
	assert spec["initialViewState"]["zoom"] == 17
	footprints = next(layer for layer in spec["layers"] if layer["id"] == "osm-buildings")
	assert footprints["extruded"] is False
	assert "effects" not in spec or not spec["effects"]
	assert rankingDeck([]) is None
