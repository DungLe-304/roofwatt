"""Tools exposed to the RoofWatt agent.

Each analysis tool takes only a buildingId and recomputes the chain below it (CoStar -> roof -> PVWatts ->
finance; PVWatts responses are cached), so the model never copies numbers between tools. Failures come back
as {"buildingId", "error"} so the agent can report them and continue with other buildings.
"""

import math
from concurrent.futures import ThreadPoolExecutor

import requests

import config
from data.costar_client import CostarClient
from data.costar_client import getBuilding as getBuildingData
from data.costar_client import searchBuildings as searchBuildingsData
from models.finance import compute_financials
from models.roof import estimate_roof
from models.solar import estimate_solar

toolErrors = (LookupError, ValueError, RuntimeError, requests.RequestException)

roofWattTools = [searchBuildingsData, getBuildingData, analyzeRoof, estimateSolar, computeFinancials, rankBuildings]
