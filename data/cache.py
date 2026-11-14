"""File cache for downloaded artifacts (Vexcel images), so the demo can run offline.

Layout: cache/<namespace>/<safe key><suffix>. cache/ is gitignored. The PVWatts cache in models/solar.py
predates this module and keeps its own layout.
"""

import re
from pathlib import Path

CACHE_ROOT = Path(__file__).resolve().parents[1] / "cache"


def _safe(key: str) -> str:
	return re.sub(r"[^A-Za-z0-9_-]", "_", key)


def find(namespace: str, key: str) -> Path | None:
	"""Return the cached file for key (any suffix), or None."""
	folder = CACHE_ROOT / namespace
	if not folder.is_dir():
		return None
	return next((path for path in sorted(folder.glob(_safe(key) + ".*")) if path.is_file()), None)


def write_bytes(namespace: str, key: str, suffix: str, data: bytes) -> Path:
	path = CACHE_ROOT / namespace / (_safe(key) + suffix)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(data)
	return path
