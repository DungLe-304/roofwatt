"""Ranked table + map for a rankBuildings result. Every number shown comes from the tool (only rounded/converted)."""

import math

import pandas as pd
import pydeck as pdk

from ui.sunlight import solarNoon, sunlightEffects

ORANGE = [255, 159, 28]  # #FF9F1C, the one accent: the #1 building
BLUE = [47, 128, 237]  # #2F80ED, data color: every other ranked building
INK = [29, 29, 31]  # #1D1D1F
PAPER = [245, 245, 247]  # #F5F5F7
LAYER_ID = "ranked"
MAP_HEIGHT_PX = 540
MAP_MIN_WIDTH_PX = 560  # narrowest map column we expect; the view is fitted to this so wider screens only add margin
MAX_ZOOM = 13
FOCUS_ZOOM = 17
PITCH_DEG = 55  # tilted so extruded OSM buildings and their shadows read as 3D (Khoa's map)
WORLD_PX = 512  # deck.gl Web Mercator: the whole world is 512 px wide at zoom 0
FLAT_ON_TOP = {"depthTest": False}  # rank dots and numbers are never hidden behind 3D buildings or each other
MAP_STYLES = {False: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
	True: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"}  # keyed by dark theme


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


def rankingDeck(rows: list[dict], selectedId: str | None = None, *, dark: bool = False, buildings = None,
		queryDate = None, city = "Houston", focusRow = None) -> pdk.Deck | None:
	"""3D map of the ranked buildings, or None when no row has coordinates.

	Points: #1 orange, the others blue, size ~ system kW, the selected one ringed. `buildings` (OSM footprints)
	are extruded by tagged height; `queryDate` lights the scene at solar noon. `focusRow` zooms to one building.
	"""
	located = [row for row in rows if row.get("lat") is not None and row.get("lon") is not None]
	if not located:
		return None
	maxKw = max(row["systemKw"] for row in located) or 1
	ring = PAPER if dark else INK
	points = [{
		"buildingId": str(row["buildingId"]),
		"position": [row["lon"], row["lat"]],
		"label": str(row["rank"]),
		"name": _name(row),
		"color": ORANGE if row["rank"] == 1 else BLUE,
		"labelColor": INK if row["rank"] == 1 else [255, 255, 255],
		"radius": round(11 + 13 * math.sqrt(max(row["systemKw"], 0) / maxKw), 1),  # area grows with kW
		"lineWidth": 4 if str(row["buildingId"]) == str(selectedId) else 1.5,
		"lineColor": ring if str(row["buildingId"]) == str(selectedId) else ([0, 0, 0] if dark else [255, 255, 255]),
		"paybackLabel": f"{row['simplePaybackYr']:.2f} yr",
		"savingsLabel": f"${row['annualSavingsUsd']:,.0f}/yr",
		"co2Label": f"{row['co2TonsPerYear']:,.0f} t CO₂/yr",
		"systemLabel": f"{row['systemKw']:,.0f} kW",
	} for row in located]
	points.sort(key = lambda point: (point["lineWidth"] > 2, -int(point["label"])))  # best ranks and the selection on top
	view = fitView([point["position"] for point in points], width_px = MAP_MIN_WIDTH_PX, height_px = MAP_HEIGHT_PX)
	view.pitch, view.bearing = PITCH_DEG, 0
	if focusRow is not None and focusRow.get("lat") is not None and focusRow.get("lon") is not None:
		view = pdk.ViewState(latitude = focusRow["lat"], longitude = focusRow["lon"], zoom = FOCUS_ZOOM, pitch = PITCH_DEG, bearing = 0)
	layers = []
	if buildings:
		# A deck.gl polygon can receive shadows; the basemap itself cannot, so a ground sheet goes under the buildings.
		vertices = [vertex for building in buildings for vertex in building["footprint"]]
		west, east = min(p[0] for p in vertices) - 0.001, max(p[0] for p in vertices) + 0.001
		south, north = min(p[1] for p in vertices) - 0.001, max(p[1] for p in vertices) + 0.001
		layers.append(pdk.Layer("PolygonLayer", [{"polygon": [[west, south], [east, south], [east, north], [west, north]]}],
			id = "shadow-ground", get_polygon = "polygon", get_fill_color = [44, 44, 46, 110] if dark else [235, 238, 240, 100],
			stroked = False, pickable = False))
		layers.append(pdk.Layer("PolygonLayer", buildings, id = "osm-buildings", get_polygon = "footprint",
			get_elevation = "heightM", extruded = True, filled = True, stroked = False,
			get_fill_color = [99, 99, 102] if dark else [174, 174, 178], material = True, pickable = False))
	layers.append(pdk.Layer("ScatterplotLayer", points, id = LAYER_ID, get_position = "position", get_fill_color = "color",
		get_radius = "radius", radius_units = "'pixels'", stroked = True, get_line_color = "lineColor",
		get_line_width = "lineWidth", line_width_units = "'pixels'", pickable = True,
		billboard = True, parameters = FLAT_ON_TOP))  # round dots facing the camera, also on the tilted map
	layers.append(pdk.Layer("TextLayer", points, get_position = "position", get_text = "label", get_color = "labelColor",
		get_size = 15, get_text_anchor = "'middle'", get_alignment_baseline = "'center'", font_weight = 700,
		parameters = FLAT_ON_TOP))
	effects = []
	if queryDate:
		sunTime = solarNoon(view.latitude, view.longitude, queryDate, city)
		effects = sunlightEffects(int(sunTime.timestamp() * 1000))
	tooltip = {"html": "<b>#{label} · {name}</b><br/>Payback <b>{paybackLabel}</b><br/>Savings {savingsLabel}"
		"<br/>{systemLabel} · {co2Label}",
		"style": {"backgroundColor": "#2C2C2E" if dark else "#FFFFFF", "color": "#F5F5F7" if dark else "#1D1D1F",
			"fontSize": "15px", "borderRadius": "10px", "border": f"1px solid {'#38383A' if dark else '#E5E5EA'}",
			"padding": "10px 12px"}}
	return pdk.Deck(layers = layers, effects = effects, initial_view_state = view, map_provider = "carto",
		map_style = MAP_STYLES[bool(dark)], tooltip = tooltip)


def selectedFromMap(selection) -> str | None:
	"""buildingId of the map point the user clicked, if any (st.pydeck_chart selection state)."""
	objects = (((selection or {}).get("selection") or {}).get("objects") or {}).get(LAYER_ID) or []
	return str(objects[0]["buildingId"]) if objects and objects[0].get("buildingId") else None


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
