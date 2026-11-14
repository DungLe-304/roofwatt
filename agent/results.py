"""Read tool results (roof images, building ranking) back out of an agent run's message history (for the UI)."""

import json
from pathlib import Path


def roofImages(messages) -> list[tuple[str, str]]:
	"""(buildingId, imagePath) for every successful getRoofImage call whose file exists, in call order, deduplicated."""
	images = []
	for message in messages:
		if getattr(message, "type", None) != "tool" or getattr(message, "name", None) != "getRoofImage":
			continue
		try:
			result = json.loads(message.content)
		except (TypeError, ValueError):
			continue
		path = result.get("imagePath") if isinstance(result, dict) else None
		image = (str(result.get("buildingId")), path)
		if path and Path(path).is_file() and image not in images:
			images.append(image)
	return images


def rankingResult(messages) -> dict | None:
	"""The result of the last successful rankBuildings call that ranked at least one building, else None."""
	for message in reversed(messages):
		if getattr(message, "type", None) != "tool" or getattr(message, "name", None) != "rankBuildings":
			continue
		try:
			result = json.loads(message.content)
		except (TypeError, ValueError):
			continue
		if isinstance(result, dict) and result.get("ranked"):
			return result
	return None
