"""Ranked table and map built from a rankBuildings result (no Streamlit, no network)."""

import json
import math

import pytest

from ui.ranking import addCoordinates, fitView, rankingDeck, rankingTable, summaryText

ROWS = [
	{"rank": 1, "address": "5959 Corporate Dr", "buildingId": "240117", "usableRoofM2": 7906.04, "systemKw": 1167.72,
	 "annualKwh": 1660572.5, "annualSavingsUsd": 142145.01, "costPerWattUsd": 1.9, "capexUsd": 2218672.19,
	 "netCapexUsd": 1553070.53, "simplePaybackYr": 10.93, "co2TonsPerYear": 552.76},
	{"rank": 2, "address": None, "buildingId": "7", "usableRoofM2": 900.0, "systemKw": 132.9,
	 "annualKwh": 190000.0, "annualSavingsUsd": 16264.0, "costPerWattUsd": 2.4, "capexUsd": 318960.0,
	 "netCapexUsd": 223272.0, "simplePaybackYr": 13.73, "co2TonsPerYear": 63.25},
]


def record(buildingId, lat, lon):
	return {"id": buildingId, "primaryAddress": {"latitude": lat, "longitude": lon}}


def test_add_coordinates_matches_ids_in_one_pass_and_keeps_rows_without_coordinates():
	records = iter([record(5, 1.0, 2.0), record(240117, 29.71, -95.55), record(7, None, -95.0)])
	rows = addCoordinates(ROWS, records)
	assert (rows[0]["lat"], rows[0]["lon"]) == (29.71, -95.55)
	assert (rows[1]["lat"], rows[1]["lon"]) == (None, None)
	assert "lat" not in ROWS[0]  # input rows are not mutated


def test_table_converts_units_and_keeps_tool_numbers():
	table = rankingTable(ROWS)
	assert list(table.columns) == ["Rank", "Address", "Building ID", "System (kW)", "Energy (MWh/yr)",
		"Savings ($/yr)", "Net cost after ITC ($)", "Payback (yr)", "CO₂ avoided (t/yr)"]
	first = table.iloc[0]
	assert first["Energy (MWh/yr)"] == 1661  # 1,660,572.5 kWh, rounded for display
	assert first["Payback (yr)"] == 10.93
	assert first["Net cost after ITC ($)"] == 1553071
	assert table.iloc[1]["Address"] == "Building 7"


def test_deck_plots_only_rows_with_coordinates_and_highlights_rank_one():
	rows = [ROWS[0] | {"lat": 29.71, "lon": -95.55}, ROWS[1] | {"lat": None, "lon": None}]
	spec = json.loads(rankingDeck(rows).to_json())
	points = spec["layers"][0]["data"]
	assert [point["buildingId"] for point in points] == ["240117"]
	assert points[0]["color"] == [0, 255, 0]  # rank 1: bright green (start of the rank gradient)
	assert points[0]["paybackLabel"] == "10.93 yr"
	assert spec["initialViewState"]["latitude"] == pytest.approx(29.71)


def test_deck_is_none_when_no_row_has_coordinates():
	assert rankingDeck([ROWS[1] | {"lat": None, "lon": None}]) is None


def test_summary_states_scope_exclusions_and_the_unsourced_usable_factor():
	result = {"city": "Houston", "propertyType": "Office", "totalMatches": 185, "rankedCount": 173,
		"excluded": {"errors": [{"buildingId": "9", "error": "x"}], "belowMinimumSize": 12, "noPayback": 0},
		"ranked": ROWS, "assumptions": {"usableFactor": 0.6, "minSystemKw": 50}}
	text = summaryText(result)
	assert "Top 2 of 173 ranked Office buildings in Houston (185 matches" in text
	assert "12 below 50 kW" in text and "1 with data errors" in text
	assert "usable roof factor 0.6 is an unsourced assumption" in text


def test_view_fits_every_point_in_the_map_frame():
	# Real top-10 spread: rank 6 sits far north of the others and was cropped by pydeck's compute_view.
	points = [[-95.55, 29.71], [-95.55, 29.68], [-95.51, 29.72], [-95.64, 29.78], [-95.40, 29.70],
		[-95.58, 29.99], [-95.56, 29.84], [-95.46, 29.76], [-95.43, 29.78], [-95.49, 29.72]]
	view = fitView(points, width_px=900, height_px=420)
	degrees_per_px = 360 / (512 * 2 ** view.zoom)  # deck.gl world is 512 px at zoom 0
	half_height_deg = 420 / 2 * degrees_per_px * math.cos(math.radians(view.latitude))
	half_width_deg = 900 / 2 * degrees_per_px
	for lon, lat in points:
		assert abs(lat - view.latitude) < half_height_deg
		assert abs(lon - view.longitude) < half_width_deg
	assert fitView([[-95.55, 29.71]], width_px=900, height_px=420).zoom == 13


def test_rank_colors_run_from_green_through_yellow_to_red_and_cover_every_rank():
	from ui.ranking import rankColors
	for count in (1, 2, 3, 10, 20):
		colors = rankColors(count)
		assert len(colors) >= count and colors[0] == [0, 255, 0]
	ten = rankColors(10)
	assert ten[4] == [204, 255, 0] and ten[5] == [255, 255, 0] and ten[9] == [255, 51, 0]
	assert rankColors(0) and rankColors(10_000)  # no division by zero, no zero step
