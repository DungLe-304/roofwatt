"""All financial and physical assumptions live here. Every value needs a source (see CLAUDE.md section 4)."""

USABLE_FACTOR = 0.6  # assumption: share of roof footprint usable for panels (tier 1)
POWER_DENSITY_KW_PER_M2 = None  # TODO: look up and cite
TILT_DEG = None  # TODO: look up and cite
PVWATTS_LOSSES_PCT = 14  # PVWatts default
ELECTRICITY_RATE_USD_PER_KWH = None  # TODO: EIA average commercial price, Texas
COST_PER_WATT_USD = None  # TODO: NREL or SEIA commercial benchmark
INCENTIVE_PCT = None  # TODO: verify current incentive rules
GRID_EF_KG_PER_KWH = None  # TODO: EPA eGRID, ERCOT (ERCT)
MIN_SYSTEM_KW = 50  # drop buildings below this size

import os
import tomllib
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values as dotenvValues
from pydantic import BaseModel, SecretStr

rootPath = Path(__file__).resolve().parent.parent

class Settings(BaseModel):
	dataMode: Literal["mock", "live"] = "mock"
	agentMode: Literal["mock", "live"] = "mock"
	costarSource: Literal["export", "api"] = "export"
	costarExportPath: Path = rootPath.parent / "CoStar Data Extract"
	modelName: str = "claude-sonnet-5-5"
	anthropicApiKey: SecretStr = SecretStr("")
	costarApiKey: SecretStr = SecretStr("")
	vexcelApiKey: SecretStr = SecretStr("")
	pvwattsApiKey: SecretStr = SecretStr("")
	geminiApiKey: SecretStr = SecretStr("")

def loadSettings() -> Settings:
	configValues = dict(dotenvValues(rootPath / ".env"))
	secretsPath = rootPath / ".streamlit" / "secrets.toml"

	if secretsPath.exists():
		with secretsPath.open("rb") as secretsFile:
			configValues.update(tomllib.load(secretsFile))

	for fieldName in Settings.model_fields:
		if fieldName in os.environ:
			configValues[fieldName] = os.environ[fieldName]

	knownValues = {fieldName: fieldValue for fieldName, fieldValue in configValues.items() if fieldName in Settings.model_fields and fieldValue is not None}
	settings = Settings(**knownValues)

	if not settings.costarExportPath.is_absolute():
		settings.costarExportPath = (rootPath / settings.costarExportPath).resolve()

	if settings.agentMode == "live" and not settings.anthropicApiKey.get_secret_value().strip():
		raise ValueError("Live agent mode requires anthropicApiKey.")

	return settings