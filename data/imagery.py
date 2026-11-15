"""Vexcel aerial (nadir orthomosaic) roof image for one building, cached on disk.

API: GET https://api.vexcelgroup.com/v2/ortho/extract, per Vexcel's OpenAPI spec
(https://api.vexcelgroup.com/v2/api-docs/ortho, read 2026-11-14): `layer` (urban, urban-r, urban-g, wide-area, graysky),
`wkt` (POINT(lon lat)), `bbox-dimensions=width,height` in meters around the point, `destination-dimensions=
width,height,fit|fill` in pixels, `image-format` (jpeg/png/tiff). Auth: our VEXCEL_API_KEY is an API key, sent as
the `api_key` query parameter (it is not a token: /auth/verify and the `token` parameter both return 401).
Responses: 200 image, 204 no coverage, 401 bad key.
"""

import os
from pathlib import Path

import requests

from data import cache

VEXCEL_EXTRACT_URL = "https://api.vexcelgroup.com/v2/ortho/extract"
VEXCEL_LAYER = "urban"
CACHE_NAMESPACE = "vexcel"


def get_roof_image(building_id: str, lat: float, lon: float, *, extent_m: float = 150, size_px: int = 640) -> Path:
	"""Return the path of a cached or freshly downloaded square image (extent_m wide, centered on lat/lon).

	Raises RuntimeError on a missing/rejected key, no coverage, or any other non-image response.
	"""
	extent = round(extent_m)
	key = f"{building_id}_{VEXCEL_LAYER}_{extent}m_{size_px}px"
	cached = cache.find(CACHE_NAMESPACE, key)
	if cached is not None:
		return cached
	apiKey = os.getenv("VEXCEL_API_KEY")
	if not apiKey:
		raise RuntimeError("VEXCEL_API_KEY is not set (see .env.example)")
	params = {
		"layer": VEXCEL_LAYER,
		"wkt": f"POINT({lon} {lat})",
		"bbox-dimensions": f"{extent},{extent}",
		"destination-dimensions": f"{size_px},{size_px},fit",
		"image-format": "jpeg",
		"api_key": apiKey,
	}
	try:
		response = requests.get(VEXCEL_EXTRACT_URL, params=params, timeout=60)
	except requests.RequestException as error:  # the message holds the URL, and Vexcel only takes the key there
		raise type(error)(str(error).replace(apiKey, "***")) from None
	contentType = response.headers.get("content-type", "")
	if response.status_code == 401:
		raise RuntimeError("Vexcel rejected VEXCEL_API_KEY (HTTP 401)")
	if response.status_code == 204:
		raise RuntimeError(f"Vexcel has no imagery for {building_id} in layer '{VEXCEL_LAYER}' (HTTP 204)")
	if response.status_code != 200 or not contentType.startswith("image/"):
		raise RuntimeError(f"Vexcel returned HTTP {response.status_code} ({contentType}): "
			f"{response.text[:200].replace(apiKey, '***')}")
	suffix = "." + contentType.split("/", 1)[1].split(";")[0].strip()
	return cache.write_bytes(CACHE_NAMESPACE, key, suffix, response.content)
