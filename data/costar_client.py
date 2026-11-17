"""Read the supplied CoStar extract; no hosted API or credentials required.

Field and enum definitions: costar-kit/schemas/commercial-property.schema.json.
Search matches primary-address city and state, not the broader research market.
"""

import csv
import json
import random
from pathlib import Path

from models.schemas import Building, SearchBuildingsInput, SearchBuildingsResult


rootPath = Path(__file__).resolve().parents[1] / "costar-kit"  # the CoStar hackathon data kit
supportedCities = {"houston": ("Houston", "TX"), "los angeles": ("Los Angeles", "CA"), "la": ("Los Angeles", "CA")}


class CostarClient:
	def __init__(self, projectPath: Path = rootPath):
		self.projectPath = Path(projectPath)
		self.recordsPath = self.projectPath / "data" / "commercial-property.jsonl"
		with (self.projectPath / "schemas" / "commercial-property.schema.json").open(encoding="utf-8") as schemaFile:
			definitions = json.load(schemaFile)["$defs"]
		self.propertyTypes = dict(zip(definitions["PropertyType"]["enum"], definitions["PropertyType"]["x-enum-varnames"]))
		self.matterportIds = {}
		mappingPath = self.projectPath / "commercial-properties.csv"
		if mappingPath.exists():
			with mappingPath.open(encoding="utf-8-sig", newline="") as mappingFile:
				for row in csv.DictReader(mappingFile):
					modelId = row["MatterportModelId"].strip()
					modelIds = self.matterportIds.setdefault(row["PropertyId"].strip(), [])
					if modelId and modelId not in modelIds:
						modelIds.append(modelId)

	def iterRecords(self):
		with self.recordsPath.open(encoding="utf-8-sig") as recordsFile:
			for lineNumber, line in enumerate(recordsFile, start=1):
				if not line.strip():
					continue
				try:
					record = json.loads(line)
					if not isinstance(record, dict) or not isinstance(record.get("id"), int):
						raise ValueError("Expected a property object with an integer id.")
				except (ValueError, TypeError) as error:
					raise ValueError(f"Invalid property record at {self.recordsPath.name}:{lineNumber}") from error
				yield record

	def mapBuilding(self, record: dict) -> Building:
		address = record.get("primaryAddress") or {}
		streetFields = ("streetNumber", "streetDirection", "streetName", "streetType", "streetSuffix")
		street = " ".join(str(address[key]).strip() for key in streetFields if address.get(key)) or None
		grossArea = record.get("grossBuildingAreaSquareFeet")
		rentableArea = record.get("rentableBuildingAreaSquareFeet")
		stories = record.get("numStoriesAboveGrade")
		typicalFloor = record.get("grossTypicalFloorSquareFeet")
		builtYears = {event["year"] for event in (record.get("constructionEvents") or []) if event.get("eventType") == 2 and event.get("year", 0) > 0}
		warnings = ["Owner name is unresolved; property contacts contain identifiers.", "Roof footprint is not measured by this adapter."]
		if grossArea is None or grossArea <= 0:
			grossArea = None
			warnings.append("Gross building area is missing or nonpositive; rentable area is kept separately.")
		if len(builtYears) > 1:
			warnings.append("Multiple construction completion years; yearBuilt is unresolved.")
		if address.get("latitude") is None or address.get("longitude") is None:
			warnings.append("Coordinates are incomplete.")
		return Building(buildingId=str(record["id"]), propertyType=self.propertyTypes.get(record.get("propertyType"), "Unknown"), address=street, city=address.get("city"), state=address.get("state"), lat=address.get("latitude"), lon=address.get("longitude"), buildingSqft=grossArea, buildingAreaSource="grossBuildingAreaSquareFeet" if grossArea is not None else None, rentableSqft=rentableArea if rentableArea is not None and rentableArea > 0 else None, typicalFloorSqft=typicalFloor if typicalFloor is not None and typicalFloor > 0 else None, stories=stories if stories is not None and stories > 0 else None, yearBuilt=next(iter(builtYears)) if len(builtYears) == 1 else None, matterportModelIds=self.matterportIds.get(str(record["id"]), []), dataWarnings=warnings)

	def iterMatches(self, city: str, propertyType: str = "Office", minSqft: float = 0):
		"""Yield every existing property record matching the filters, in dataset order, without a limit."""
		query = SearchBuildingsInput(city=city, propertyType=propertyType, minSqft=minSqft)
		cityKey = query.city.strip().casefold()
		if cityKey not in supportedCities:
			raise ValueError("Supported cities: Houston and Los Angeles.")
		cityName, stateName = supportedCities[cityKey]
		typeCodes = {name.casefold(): code for code, name in self.propertyTypes.items()}
		typeKey = query.propertyType.strip().casefold()
		if typeKey not in typeCodes:
			raise ValueError(f"Unknown property type: {query.propertyType}. Use a documented CoStar property type.")
		seenIds = set()
		for record in self.iterRecords():
			address = record.get("primaryAddress") or {}
			if (address.get("city") or "").casefold() != cityName.casefold() or (address.get("state") or "").upper() != stateName:
				continue
			if record.get("propertyType") != typeCodes[typeKey] or record.get("constructionStatus") != 1:
				continue
			grossArea = record.get("grossBuildingAreaSquareFeet")
			if query.minSqft > 0 and (grossArea is None or grossArea < query.minSqft):
				continue
			if record["id"] in seenIds:
				continue
			seenIds.add(record["id"])
			yield record

	def allBuildings(self, city: str, propertyType: str = "Office", minSqft: float = 0) -> list[Building]:
		return [self.mapBuilding(record) for record in self.iterMatches(city, propertyType, minSqft)]

	def searchBuildings(self, city: str, propertyType: str = "Office", minSqft: float = 0, limit: int = 10, randomize: bool = False) -> SearchBuildingsResult:
		normalizedPropertyType = propertyType.strip() if propertyType else "Office"
		query = SearchBuildingsInput(city=city, propertyType=normalizedPropertyType or "Office", minSqft=minSqft, limit=limit, randomize=randomize)
		matchingRecords = list(self.iterMatches(query.city, query.propertyType, query.minSqft))
		totalMatches = len(matchingRecords)
		if query.randomize:
			selectedRecords = random.SystemRandom().sample(matchingRecords, min(query.limit, totalMatches))
		else:
			selectedRecords = matchingRecords[:query.limit]
		buildings = [self.mapBuilding(record) for record in selectedRecords]
		warnings = ["Results were selected randomly and are not ranked by solar profitability." if query.randomize else "Results follow dataset order; they are not ranked by solar profitability."]
		if totalMatches < query.limit:
			warnings.append(f"Only {totalMatches} buildings match the requested filters.")
		return SearchBuildingsResult(buildings=buildings, totalMatches=totalMatches, warnings=warnings)

	def getBuilding(self, buildingId: str) -> Building:
		for record in self.iterRecords():
			if str(record["id"]) == str(buildingId):
				return self.mapBuilding(record)
		raise LookupError(f"Building {buildingId} is absent from the CoStar extract.")


def searchBuildings(city: str, propertyType: str = "Office", minSqft: float = 0, limit: int = 10, randomize: bool = False) -> SearchBuildingsResult:
	"""Search existing CoStar properties by city, type, and minimum gross area.

	Set randomize to true to sample matching properties randomly. A blank propertyType defaults to Office.
	Results are never ranked by solar profitability.
	"""
	return CostarClient().searchBuildings(city, propertyType, minSqft, limit, randomize)


def getBuilding(buildingId: str) -> Building:
	"""_summary_

	Args:
		buildingId (str): _description_

	Returns:
		Building: _description_

	Return the CoStar property matching buildingId.
	Raise LookupError if the ID is absent from the local extract.
	"""
	return CostarClient().getBuilding(buildingId)
