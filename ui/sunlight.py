"""City-local dates for ranking query metadata."""

from datetime import datetime
from zoneinfo import ZoneInfo


def cityTimezone(city):
	return "America/Los_Angeles" if city.casefold() in ("los angeles", "la") else "America/Chicago"


def queryDateFor(city, submittedAt):
	return datetime.fromisoformat(submittedAt).astimezone(ZoneInfo(cityTimezone(city))).date().isoformat()
