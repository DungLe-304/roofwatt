"""Shared data contracts supporting both legacy snake_case and API camelCase."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Building(Contract):
    buildingId: str = Field(validation_alias=AliasChoices("buildingId", "building_id"))
    propertyType: str = Field(validation_alias=AliasChoices("propertyType", "property_type"))
    address: str | None = None
    city: str | None = None
    state: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    buildingSqft: float | None = Field(default=None, gt=0, validation_alias=AliasChoices("buildingSqft", "building_sqft"))
    buildingAreaSource: str | None = None
    rentableSqft: float | None = Field(default=None, gt=0)
    typicalFloorSqft: float | None = Field(default=None, gt=0, validation_alias=AliasChoices("typicalFloorSqft", "typical_floor_sqft"))
    footprintM2: float | None = Field(default=None, gt=0, validation_alias=AliasChoices("footprintM2", "footprint_m2"))
    stories: int | None = None
    yearBuilt: int | None = Field(default=None, validation_alias=AliasChoices("yearBuilt", "year_built"))
    ownerName: str | None = Field(default=None, validation_alias=AliasChoices("ownerName", "owner_name"))
    matterportModelIds: list[str] = Field(default_factory=list)
    dataWarnings: list[str] = Field(default_factory=list)
    source: str = "costar-extract"

    @property
    def building_id(self) -> str: return self.buildingId
    @property
    def property_type(self) -> str: return self.propertyType
    @property
    def building_sqft(self) -> float | None: return self.buildingSqft
    @property
    def typical_floor_sqft(self) -> float | None: return self.typicalFloorSqft
    @property
    def footprint_m2(self) -> float | None: return self.footprintM2
    @property
    def year_built(self) -> int | None: return self.yearBuilt
    @property
    def owner_name(self) -> str | None: return self.ownerName


class SearchBuildingsInput(Contract):
    city: str
    propertyType: str = "Office"
    minSqft: float = Field(default=0, ge=0)
    limit: int = Field(default=10, ge=1, le=100)
    randomize: bool = False


class SearchBuildingsResult(Contract):
    buildings: list[Building]
    totalMatches: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class RoofResult(Contract):
    buildingId: str = Field(validation_alias=AliasChoices("buildingId", "building_id"))
    usableRoofM2: float = Field(ge=0, validation_alias=AliasChoices("usableRoofM2", "usable_roof_m2"))
    method: str
    imagePath: str | None = Field(default=None, validation_alias=AliasChoices("imagePath", "image_path"))

    @property
    def building_id(self) -> str: return self.buildingId
    @property
    def usable_roof_m2(self) -> float: return self.usableRoofM2
    @property
    def image_path(self) -> str | None: return self.imagePath


class SolarResult(Contract):
    buildingId: str = Field(validation_alias=AliasChoices("buildingId", "building_id"))
    systemKw: float = Field(ge=0, validation_alias=AliasChoices("systemKw", "system_kw"))
    annualKwh: float = Field(ge=0, validation_alias=AliasChoices("annualKwh", "annual_kwh"))

    @property
    def building_id(self) -> str: return self.buildingId
    @property
    def system_kw(self) -> float: return self.systemKw
    @property
    def annual_kwh(self) -> float: return self.annualKwh


class FinanceResult(Contract):
    buildingId: str = Field(validation_alias=AliasChoices("buildingId", "building_id"))
    annualSavingsUsd: float = Field(ge=0, validation_alias=AliasChoices("annualSavingsUsd", "annual_savings_usd"))
    capexUsd: float = Field(ge=0, validation_alias=AliasChoices("capexUsd", "capex_usd"))
    netCapexUsd: float = Field(ge=0, validation_alias=AliasChoices("netCapexUsd", "net_capex_usd"))
    simplePaybackYr: float | None = Field(default=None, ge=0, validation_alias=AliasChoices("simplePaybackYr", "simple_payback_yr"))
    co2TonsPerYear: float = Field(ge=0, validation_alias=AliasChoices("co2TonsPerYear", "co2_tons_per_year"))

    @property
    def building_id(self) -> str: return self.buildingId
    @property
    def annual_savings_usd(self) -> float: return self.annualSavingsUsd
    @property
    def capex_usd(self) -> float: return self.capexUsd
    @property
    def net_capex_usd(self) -> float: return self.netCapexUsd
    @property
    def simple_payback_yr(self) -> float | None: return self.simplePaybackYr
    @property
    def co2_tons_per_year(self) -> float: return self.co2TonsPerYear
