import json

import pytest
from pydantic import ValidationError

from data.costar_client import CostarClient, rootPath


@pytest.fixture
def client(tmp_path):
	(tmp_path / "data").mkdir()
	(tmp_path / "schemas").mkdir()
	(tmp_path / "schemas" / "commercial-property.schema.json").write_bytes((rootPath / "schemas" / "commercial-property.schema.json").read_bytes())
	baseRecord = {"id": 1, "propertyType": 5, "constructionStatus": 1, "primaryAddress": {"city": "Houston", "state": "TX", "streetNumber": "10", "streetName": "Example"}, "grossBuildingAreaSquareFeet": 100, "constructionEvents": [{"eventType": 2, "year": 1980}, {"eventType": 4, "year": 2020}]}
	records = [baseRecord, dict(baseRecord, id=2, grossBuildingAreaSquareFeet=None, rentableBuildingAreaSquareFeet=500), dict(baseRecord, id=3, constructionStatus=2), dict(baseRecord, id=4, propertyType=2), dict(baseRecord, id=5, primaryAddress={"city": "Houston", "state": "CA"}), dict(baseRecord, id=6, primaryAddress={"city": "Los Angeles", "state": "CA"})]
	(tmp_path / "data" / "commercial-property.jsonl").write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
	(tmp_path / "commercial-properties.csv").write_text("PropertyId,MatterportModelId\n1,modelA\n1,modelB\n1,modelA\n", encoding="utf-8")
	return CostarClient(tmp_path)


def testFiltersAndLimit(client):
	result = client.searchBuildings(" houston ", "office", limit=1)
	assert result.totalMatches == 2
	assert [building.buildingId for building in result.buildings] == ["1"]
	assert client.searchBuildings("LA").buildings[0].buildingId == "6"


def testMissingAreaIsNotReplacedByRentableArea(client):
	result = client.searchBuildings("Houston", minSqft=1)
	assert [building.buildingId for building in result.buildings] == ["1"]
	building = client.getBuilding("2")
	assert building.buildingSqft is None
	assert building.rentableSqft == 500
	assert building.ownerName is None
	assert building.footprintM2 is None
	assert building.lat is None


def testConstructionYearAndMatterportJoin(client):
	building = client.getBuilding("1")
	assert building.yearBuilt == 1980
	assert building.matterportModelIds == ["modelA", "modelB"]


def testEmptyAndInvalidRequests(client):
	assert client.searchBuildings("Houston", minSqft=101).totalMatches == 0
	with pytest.raises(ValueError, match="Supported cities"):
		client.searchBuildings("Boston")
	with pytest.raises(ValueError, match="Unknown property type"):
		client.searchBuildings("Houston", "typo")
	with pytest.raises(ValidationError):
		client.searchBuildings("Houston", limit=0)
	with pytest.raises(LookupError):
		client.getBuilding("missing")


def testMalformedRecordReportsLine(client):
	client.recordsPath.write_text("{}\n", encoding="utf-8")
	with pytest.raises(ValueError, match="commercial-property.jsonl:1"):
		client.searchBuildings("Houston")
