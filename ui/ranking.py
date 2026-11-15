"""Ranked table + map for a rankBuildings result. Every number shown comes from the tool (only rounded/converted)."""

import math

import pandas as pd
import pydeck as pdk

from data.buildings import loadBuildingGeometry
from ui.sunlight import solarNoon, sunlightEffects

LABEL_COLOR = [15, 23, 42]  # design-system "on accent" #0F172A
MAP_HEIGHT_PX = 420
MAP_MIN_WIDTH_PX = 700  # narrowest chat column we expect; the view is fitted to this so wider screens only add margin
MAX_ZOOM = 13
WORLD_PX = 512  # deck.gl Web Mercator: the whole world is 512 px wide at zoom 0


def addCoordinates(rows: list[dict], records) -> list[dict]:
	"""Copy of rows with lat/lon from CoStar records (one pass over `records`); None when a building has none."""
	wanted = {str(row["buildingId"]) for row in rows}
	found = {}
	for record in records:
		buildingId = str(record.get("id"))
		if buildingId in wanted:
			address = record.get("primaryAddress") or {}
			lat, lon = address.get("latitude"), address.get("longitude")
			found[buildingId] = (lat, lon) if lat is not None and lon is not None else (None, None)
			if len(found) == len(wanted):
				break
	return [row | dict(zip(("lat", "lon"), found.get(str(row["buildingId"]), (None, None)))) for row in rows]


def _name(row: dict) -> str:
	return row.get("address") or f"Building {row['buildingId']}"


def rankingTable(rows: list[dict]) -> pd.DataFrame:
	return pd.DataFrame([{
		"Rank": row["rank"],
		"Address": _name(row),
		"Building ID": str(row["buildingId"]),
		"System (kW)": round(row["systemKw"]),
		"Energy (MWh/yr)": round(row["annualKwh"] / 1000),
		"Savings ($/yr)": round(row["annualSavingsUsd"]),
		"Net cost after ITC ($)": round(row["netCapexUsd"]),
		"Payback (yr)": row["simplePaybackYr"],
		"CO₂ avoided (t/yr)": round(row["co2TonsPerYear"]),
	} for row in rows])


def fitView(positions: list[list[float]], *, width_px: float, height_px: float, padding: float = 1.4) -> pdk.ViewState:
	"""Web-Mercator view centred on the bounding box of [lon, lat] positions, zoomed so all fit with `padding`."""
	lons, lats = [lon for lon, _ in positions], [lat for _, lat in positions]
	lon, lat = (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2
	zooms = [MAX_ZOOM]
	lonSpan = (max(lons) - min(lons)) * padding
	latSpan = (max(lats) - min(lats)) * padding / math.cos(math.radians(lat))  # Mercator stretches latitude
	for span, pixels in ((lonSpan, width_px), (latSpan, height_px)):
		if span > 0:
			zooms.append(math.log2(pixels * 360 / (WORLD_PX * span)))
	return pdk.ViewState(latitude = lat, longitude = lon, zoom = round(min(zooms), 2))


def rankingDeck(rows: list[dict], *, buildings = None, queryDate = None, city = "Houston", focusRow = None) -> pdk.Deck | None:
	"""Map of the ranked buildings (rank 1 highlighted), or None when no row has coordinates."""
	if not rows:
		return None
	TOP_HALF_COLOUR = [[i, 255, 0] for i in range(0, 255, max(1, math.floor(255 / (len(rows) / 2))))]  # gradient from bright green to yellow
	BOTTOM_HALF_COLOUR = [[255, 255 - i, 0] for i in range(0, 255, max(1, math.floor(255 / (len(rows) / 2))))]  # gradient from yellow to red
	COLOUR = TOP_HALF_COLOUR + BOTTOM_HALF_COLOUR
	points = [{
		"buildingId": str(row["buildingId"]),
		"position": [row["lon"], row["lat"]],
		"label": str(row["rank"]),
		"name": _name(row),
		"color": COLOUR[row["rank"] - 1] if 1 <= row["rank"] <= len(COLOUR) else [128, 128, 128],
		"paybackLabel": f"{row['simplePaybackYr']:.2f} yr",
		"savingsLabel": f"${row['annualSavingsUsd']:,.0f}/yr",
		"co2Label": f"{row['co2TonsPerYear']:,.0f} t CO₂/yr",
		"systemLabel": f"{row['systemKw']:,.0f} kW",
	} for row in rows if row.get("lat") is not None and row.get("lon") is not None]
	if not points:
		return None
	view = fitView([point["position"] for point in points], width_px = MAP_MIN_WIDTH_PX, height_px = MAP_HEIGHT_PX)
	view.pitch = 55
	view.bearing = 0
	if focusRow is not None and focusRow.get("lat") is not None and focusRow.get("lon") is not None:
		view = pdk.ViewState(latitude = focusRow["lat"], longitude = focusRow["lon"], zoom = 17, pitch = 55, bearing = 0)
	dots = pdk.Layer("ScatterplotLayer", points, get_position = "position", get_fill_color = "color", get_radius = 14,
		radius_units = "'pixels'", stroked = True, get_line_color = [15, 23, 42], line_width_min_pixels = 2, pickable = True)
	labels = pdk.Layer("TextLayer", points, get_position = "position", get_text = "label", get_color = LABEL_COLOR,
		get_size = 14, get_text_anchor =  "'middle'", get_alignment_baseline = "'center'", font_weight = 700)
	tooltip = {"html": "<b>#{label} {name}</b><br/>Payback {paybackLabel}<br/>{savingsLabel} · {systemLabel}<br/>{co2Label}",
		"style": {"backgroundColor": "#1B2336", "color": "#F8FAFC", "fontSize": "13px"}}
	layers = []
	if buildings:
		layers.append(pdk.Layer("PolygonLayer", buildings, id = "osm-buildings", get_polygon = "footprint", get_elevation = "heightM", extruded = True, filled = True, stroked = False, get_fill_color = [148, 163, 184], material = True, pickable = False))
		# A deck.gl polygon can receive shadows; the basemap itself cannot.
		vertices = [vertex for building in buildings for vertex in building["footprint"]]
		west, east = min(p[0] for p in vertices) - 0.001, max(p[0] for p in vertices) + 0.001
		south, north = min(p[1] for p in vertices) - 0.001, max(p[1] for p in vertices) + 0.001
		layers.insert(0, pdk.Layer("PolygonLayer", [{"polygon": [[west, south], [east, south], [east, north], [west, north]]}], id = "shadow-ground", get_polygon = "polygon", get_fill_color = [235, 238, 240, 100], stroked = False, pickable = False))
	layers.extend([dots, labels])
	effects = []
	if queryDate:
		sunTime = solarNoon(view.latitude, view.longitude, queryDate, city)
		effects = sunlightEffects(int(sunTime.timestamp() * 1000))
	return pdk.Deck(layers = layers, effects = effects, initial_view_state = view, map_provider = "carto", map_style = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json", tooltip = tooltip)


def summaryText(result: dict) -> str:
	excluded, assumptions = result.get("excluded", {}), result.get("assumptions", {})
	notes = [f"{result['totalMatches']} matches"]
	if excluded.get("belowMinimumSize"):
		notes.append(f"{excluded['belowMinimumSize']} below {assumptions.get('minSystemKw', '?')} kW")
	if excluded.get("errors"):
		notes.append(f"{len(excluded['errors'])} with data errors")
	if excluded.get("noPayback"):
		notes.append(f"{excluded['noPayback']} with no payback")
	text = (f"Top {len(result['ranked'])} of {result['rankedCount']} ranked {result['propertyType']} buildings in "
		f"{result['city']} ({'; '.join(notes)}). Payback = net cost after incentives ÷ annual savings")
	if "usableFactor" in assumptions:
		text += f"; usable roof factor {assumptions['usableFactor']} is an unsourced assumption"
	return text + "."


def showRanking(result: dict, *, key: str):
	"""Caption, map and a single-row-selectable table; returns the table's selection state."""
	import streamlit as st

	st.caption(summaryText(result))
	rows = result["ranked"]
	validRows = [row for row in rows if row.get("lat") is not None and row.get("lon") is not None]
	@st.cache_data(ttl = 300, show_spinner = False)
	def cachedGeometry(positions):
		return loadBuildingGeometry(positions)
	geometry = cachedGeometry(tuple((row["lon"], row["lat"]) for row in validRows))
	if geometry["warning"]:
		st.caption(geometry["warning"])
	options = [None] + list(range(len(validRows)))
	focusIndex = st.selectbox("3D building view", options, format_func = lambda index: "All results" if index is None else _name(validRows[index]), key = f"{key}-focus")
	focusRow = None if focusIndex is None else validRows[focusIndex]
	deck = rankingDeck(rows, buildings = geometry["buildings"], queryDate = result.get("queryDate"), city = result["city"], focusRow = focusRow)
	if deck is not None:
		st.pydeck_chart(deck, height=MAP_HEIGHT_PX)
		if result.get("queryDate"):
			sunTime = solarNoon(deck.initial_view_state.latitude, deck.initial_view_state.longitude, result["queryDate"], result["city"])
			st.caption(f"Sun position at solar noon on {result['queryDate']}: {sunTime:%H:%M %Z}. Visual simulation; weather and energy calculations are unchanged.")
		knownHeights = sum(building["heightM"] > 0 for building in geometry["buildings"])
		st.caption(f"© OpenStreetMap contributors (ODbL): {len(geometry['buildings'])} nearby footprints, {knownHeights} with tagged heights; unknown heights shown flat. Nearby footprints are not verified CoStar property boundaries. Select a property above to inspect in 3D.")
	number = st.column_config.NumberColumn
	st.caption("Select a row to see that building's roof and numbers below.")
	return st.dataframe(rankingTable(result["ranked"]), hide_index=True, width="stretch", key=key,
		on_select="rerun", selection_mode="single-row", column_config={
		"Rank": number(width="small"),
		"System (kW)": number(format="localized"),
		"Energy (MWh/yr)": number(format="localized"),
		"Savings ($/yr)": number(format="localized"),
		"Net cost after ITC ($)": number(format="localized"),
		"Payback (yr)": number(format="%.2f"),
		"CO₂ avoided (t/yr)": number(format="localized"),
	})
