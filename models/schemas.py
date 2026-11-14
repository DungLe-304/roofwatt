"""Shared contracts. Areas are square metres unless explicitly named Sqft."""

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
	model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Building(Contract):
	buildingId: str
	propertyType: str
	address: str | None = None
	city: str | None = None
	state: str | None = None
	lat: float | None = Field(default=None, ge=-90, le=90)
	lon: float | None = Field(default=None, ge=-180, le=180)
	buildingSqft: float | None = Field(default=None, gt=0)
	buildingAreaSource: str | None = None
	rentableSqft: float | None = Field(default=None, gt=0)
	footprintM2: float | None = Field(default=None, gt=0)
	stories: int | None = Field(default=None, gt=0)
	yearBuilt: int | None = Field(default=None, gt=0)
	ownerName: str | None = None
	matterportModelIds: list[str] = Field(default_factory=list)
	dataWarnings: list[str] = Field(default_factory=list)
	source: str = "costar-extract"


class SearchBuildingsInput(Contract):
	city: str
	propertyType: str = "Office"
	minSqft: float = Field(default=0, ge=0)
	limit: int = Field(default=10, ge=1, le=100)


class SearchBuildingsResult(Contract):
	buildings: list[Building]
	totalMatches: int = Field(ge=0)
	warnings: list[str] = Field(default_factory=list)


class RoofResult(Contract):
	buildingId: str
	usableRoofM2: float = Field(ge=0)
	method: str
	imagePath: str | None = None


class SolarResult(Contract):
	buildingId: str
	systemKw: float = Field(ge=0)
	annualKwh: float = Field(ge=0)


class FinanceResult(Contract):
	buildingId: str
	annualSavingsUsd: float = Field(ge=0)
	capexUsd: float = Field(ge=0)
	netCapexUsd: float = Field(ge=0)
	simplePaybackYr: float | None = Field(default=None, ge=0)
	co2TonsPerYear: float = Field(ge=0)
