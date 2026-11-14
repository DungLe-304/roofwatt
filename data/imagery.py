"""Vexcel aerial (nadir orthomosaic) roof image for one building, cached on disk.

Request format from Vexcel's "Extract Large Orthomosaic Tiles" announcement (ExtractOrthoImages, center point +
zoom + pixel size, token as `authtoken`): https://vexceldata.com/stories/new-feature-for-api-extract-large-orthomosaic-tiles/
Full reference is behind Vexcel's support login. Host and collection are unconfirmed: the token we have was
rejected (HTTP 401) by api.gic.org and api.vexcelgroup.com on 2026-11-14.
"""

import os
from pathlib import Path

import requests

from data import cache

VEXCEL_EXTRACT_URL = "https://api.gic.org/images/ExtractOrthoImages/bluesky-ultra"
CACHE_NAMESPACE = "vexcel"


def get_roof_image(building_id: str, lat: float, lon: float, *, zoom: int = 20, size_px: int = 640) -> Path:
	"""Return the path of a cached or freshly downloaded image centered on (lat, lon). Raises RuntimeError."""
	key = f"{building_id}_z{zoom}_{size_px}"
	cached = cache.find(CACHE_NAMESPACE, key)
	if cached is not None:
		return cached
	token = os.getenv("VEXCEL_API_KEY")
	if not token:
		raise RuntimeError("VEXCEL_API_KEY is not set (see .env.example)")
	params = dict(ycoordinate=lat, xcoordinate=lon, zoom=zoom, width=size_px, height=size_px, EPSG=4326, authtoken=token)
	response = requests.get(VEXCEL_EXTRACT_URL, params=params, timeout=30)
	contentType = response.headers.get("content-type", "")
	if response.status_code == 401:
		raise RuntimeError("Vexcel rejected the token (HTTP 401); get a fresh token for VEXCEL_API_KEY")
	if response.status_code != 200 or not contentType.startswith("image/"):
		raise RuntimeError(f"Vexcel returned HTTP {response.status_code} ({contentType}): {response.text[:200]}")
	suffix = "." + contentType.split("/", 1)[1].split(";")[0].strip()
	return cache.write_bytes(CACHE_NAMESPACE, key, suffix, response.content)
