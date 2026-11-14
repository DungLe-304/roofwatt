from deepagents import create_deep_agent
from data.costar_client import searchBuildings as searchBuildingsData, getBuilding as getBuildingData

agent = create_deep_agent(model = "google_genai:gemini-4-hydrogen", tools=[searchBuildingsData, getBuildingData],)