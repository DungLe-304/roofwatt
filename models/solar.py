"""Annual energy from NREL PVWatts v8, with an on-disk cache and HTTP 429 retries.

NREL is now the National Laboratory of the Rockies; developer.nrel.gov no longer resolves,
the v8 API lives at developer.nlr.gov (verified 2026-11-14).
"""

import hashlib
import json
import os
import time
from pathlib import Path

import requests

import config
from models.schemas import SolarResult

PVWATTS_URL = "https://developer.nlr.gov/api/pvwatts/v8.json"
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "pvwatts"
MAX_ATTEMPTS = 4


def estimate_solar(building_id: str, lat: float, lon: float, system_kw: float, *,
                   tilt_deg: float, losses_pct: float = config.PVWATTS_LOSSES_PCT) -> SolarResult:
    params = {
        "system_capacity": system_kw,
        "module_type": 0,   # standard
        "array_type": 1,    # fixed, roof mount
        "tilt": tilt_deg,
        "azimuth": 180,     # due south
        "losses": losses_pct,
        "lat": lat,
        "lon": lon,
    }
    key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        outputs = json.loads(cache_file.read_text())
    else:
        outputs = _fetch(params)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(outputs))
    return SolarResult(building_id=building_id, system_kw=system_kw,
                       annual_kwh=outputs["ac_annual"])


def _fetch(params: dict) -> dict:
    api_key = os.getenv("NREL_API_KEY")
    if not api_key:
        raise RuntimeError("NREL_API_KEY is not set (see .env.example)")
    for attempt in range(MAX_ATTEMPTS):
        resp = requests.get(PVWATTS_URL, params={**params, "api_key": api_key}, timeout=30)
        if resp.status_code != 429 or attempt == MAX_ATTEMPTS - 1:
            break
        time.sleep(2 ** attempt)
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"PVWatts error: {body['errors']}")
    return body["outputs"]
