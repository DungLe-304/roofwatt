"""Solar-noon timestamps for the city-local date when a query was submitted."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import noon


def cityTimezone(city):
	return "America/Los_Angeles" if city.casefold() in ("los angeles", "la") else "America/Chicago"


def queryDateFor(city, submittedAt):
	return datetime.fromisoformat(submittedAt).astimezone(ZoneInfo(cityTimezone(city))).date().isoformat()


def solarNoon(latitude, longitude, queryDate, city):
	return noon(Observer(latitude = latitude, longitude = longitude), date = date.fromisoformat(queryDate), tzinfo = ZoneInfo(cityTimezone(city)))


def sunlightEffects(timestampMs):
	# PyDeck 0.9.x JSON effects API; see its official PolygonLayer example.
	return [{"@@type": "LightingEffect", "shadowColor": [0, 0, 0, 0.35], "ambientLight": {"@@type": "AmbientLight", "intensity": 0.5}, "directionalLights": [{"@@type": "_SunLight", "timestamp": timestampMs, "color": [255, 255, 255], "intensity": 1.0, "_shadow": True}]}]
