"""Ranked table + map for a rankBuildings result. Every number shown comes from the tool (only rounded/converted)."""

import math

import pandas as pd
import pydeck as pdk

NAVY = [19, 41, 75]  # brand navy #13294B: rank labels and the selected building's ring
WHITE = [255, 255, 255]
NO_RANK_COLOR = [128, 128, 128]
LAYER_ID = "buildings"
MAP_HEIGHT_PX = 560
MAP_MIN_WIDTH_PX = 620  # narrowest map column we expect (60% of a laptop screen); wider screens only add margin
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


def rankColors(count: int) -> list[list[int]]:
	"""Khoa's rank gradient (347ae98): bright green (best) -> yellow -> red over `count` ranks."""
	step = max(1, math.floor(255 / (max(count, 1) / 2)))
	topHalf = [[i, 255, 0] for i in range(0, 255, step)]  # green -> yellow
	bottomHalf = [[255, 255 - i, 0] for i in range(0, 255, step)]  # yellow -> red
	return topHalf + bottomHalf


def rankingDeck(rows: list[dict], selectedId: str | None = None) -> pdk.Deck | None:
	"""Light map of the ranked buildings: size ~ system kW, color by rank (green best -> red), selected one ringed in navy."""
	located = [row for row in rows if row.get("lat") is not None and row.get("lon") is not None]
	if not located:
		return None
	maxKw = max(row["systemKw"] for row in located) or 1
	colors = rankColors(len(rows))
	points = [{
		"buildingId": str(row["buildingId"]),
		"position": [row["lon"], row["lat"]],
		"label": str(row["rank"]),
		"name": _name(row),
		"color": colors[row["rank"] - 1] if 1 <= row["rank"] <= len(colors) else NO_RANK_COLOR,
		"radius": round(11 + 13 * math.sqrt(max(row["systemKw"], 0) / maxKw), 1),  # area grows with kW
		"lineWidth": 4 if str(row["buildingId"]) == str(selectedId) else 1.5,
		"lineColor": NAVY if str(row["buildingId"]) == str(selectedId) else WHITE,
		"paybackLabel": f"{row['simplePaybackYr']:.2f} yr",
		"savingsLabel": f"${row['annualSavingsUsd']:,.0f}/yr",
		"co2Label": f"{row['co2TonsPerYear']:,.0f} t CO₂/yr",
		"systemLabel": f"{row['systemKw']:,.0f} kW",
	} for row in located]
	points.sort(key=lambda point: (point["lineColor"] == NAVY, -int(point["label"])))  # best ranks and the selection on top
	view = fitView([point["position"] for point in points], width_px=MAP_MIN_WIDTH_PX, height_px=MAP_HEIGHT_PX)
	dots = pdk.Layer("ScatterplotLayer", points, id=LAYER_ID, get_position="position", get_fill_color="color",
		get_radius="radius", radius_units="'pixels'", stroked=True, get_line_color="lineColor",
		get_line_width="lineWidth", line_width_units="'pixels'", pickable=True, opacity=0.95)
	labels = pdk.Layer("TextLayer", points, get_position="position", get_text="label", get_color=NAVY,
		get_size=15, get_text_anchor="'middle'", get_alignment_baseline="'center'", font_weight=700)
	tooltip = {"html": "<b>#{label} · {name}</b><br/>Payback <b>{paybackLabel}</b><br/>Savings {savingsLabel}"
		"<br/>{systemLabel} · {co2Label}",
		"style": {"backgroundColor": "#FFFFFF", "color": "#13294B", "fontSize": "15px", "borderRadius": "10px",
			"boxShadow": "0 4px 14px rgba(19,41,75,0.18)", "padding": "10px 12px"}}
	return pdk.Deck(layers=[dots, labels], initial_view_state=view, map_provider="carto", map_style="light", tooltip=tooltip)


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
