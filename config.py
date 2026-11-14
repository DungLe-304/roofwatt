"""Application settings plus shared financial and physical assumptions."""

import os
import tomllib
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, SecretStr

# Load API keys from the repo-root .env into os.environ on first import.
# Variables already set in the shell win (override=False), so tests and CI can set their own.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

rootPath = Path(__file__).resolve().parent


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
    configValues = dict(dotenv_values(rootPath / ".env"))
    secretsPath = rootPath / ".streamlit" / "secrets.toml"

    if secretsPath.exists():
        with secretsPath.open("rb") as secretsFile:
            configValues.update(tomllib.load(secretsFile))

    for fieldName in Settings.model_fields:
        if fieldName in os.environ:
            configValues[fieldName] = os.environ[fieldName]

    knownValues = {
        fieldName: fieldValue
        for fieldName, fieldValue in configValues.items()
        if fieldName in Settings.model_fields and fieldValue is not None
    }
    settings = Settings(**knownValues)

    if not settings.costarExportPath.is_absolute():
        settings.costarExportPath = (rootPath / settings.costarExportPath).resolve()

    if settings.agentMode == "live" and not settings.anthropicApiKey.get_secret_value().strip():
        raise ValueError("Live agent mode requires anthropicApiKey.")

    return settings

USABLE_FACTOR = 0.6  # assumption: share of roof footprint usable for panels (tier 1)
POWER_DENSITY_KW_PER_M2 = None  # TODO: look up and cite
TILT_DEG = None  # TODO: look up and cite
PVWATTS_LOSSES_PCT = 14  # PVWatts default
ELECTRICITY_RATE_USD_PER_KWH = None  # TODO: EIA average commercial price, Texas
COST_PER_WATT_USD = None  # TODO: NREL or SEIA commercial benchmark
INCENTIVE_PCT = None  # TODO: verify current incentive rules
GRID_EF_KG_PER_KWH = None  # TODO: EPA eGRID, ERCOT (ERCT)
MIN_SYSTEM_KW = 50  # drop buildings below this size
