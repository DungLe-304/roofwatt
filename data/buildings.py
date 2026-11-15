"""Nearby OSM building ways for visualization, not CoStar property boundaries.

Source: https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL
Only tagged metric heights are extruded. Missing heights remain flat.
"""

import hashlib
import json
import math
import re

import requests

from data.cache import find, write_bytes


def parseHeight(value):
	match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:m)?\s*", str(value or ""))
	return float(match.group(1)) if match else None


def buildingPolygons(payload):
	rows = []
	for element in payload.get("elements", []):
		geometry = element.get("geometry") or []
		polygon = [[point["lon"], point["lat"]] for point in geometry if "lon" in point and "lat" in point]
		if len(polygon) < 4 or polygon[0] != polygon[-1]:
			continue
		tags = element.get("tags") or {}
		height = parseHeight(tags.get("height"))
		rows.append({"footprint": polygon, "heightM": height or 0, "name": tags.get("name", "OSM building"), "heightLabel": f"{height:g} m (OSM tag)" if height is not None else "Unknown; shown flat", "osmId": str(element["id"])})
	return rows


def loadBuildingGeometry(positions):
	"""One bounded Overpass query, cached on disk; return geometry plus a visible status."""
	positions = sorted({(float(lon), float(lat)) for lon, lat in positions if math.isfinite(lon) and math.isfinite(lat)})[:20]
	if not positions:
		return {"buildings": [], "warning": "No property coordinates available."}
	queryParts = [f'way["building"](around:150,{lat:.6f},{lon:.6f});' for lon, lat in positions]
	query = "[out:json][timeout:15];(" + "".join(queryParts) + ");out geom;"
	cacheKey = hashlib.sha256(query.encode()).hexdigest()
	try:
		cached = find("osm-buildings", cacheKey)
		if cached:
			payload = json.loads(cached.read_text(encoding = "utf-8"))
		else:
			response = requests.post("https://overpass-api.de/api/interpreter", data = {"data": query}, timeout = 20, headers = {"User-Agent": "RoofWatt/0.1 building-map"})
			response.raise_for_status()
			payload = response.json()
			if not payload.get("remark"):
				write_bytes("osm-buildings", cacheKey, ".json", json.dumps(payload).encode())
		rows = buildingPolygons(payload)
		return {"buildings": rows, "warning": str(payload.get("remark") or ("No nearby building footprints were returned." if not rows else ""))}
	except (requests.RequestException, ValueError, OSError) as error:
		return {"buildings": [], "warning": f"Building geometry unavailable: {error}"}
