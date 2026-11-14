from deepagents import Agent, create_deep_agent
from data.costar_client import searchBuildings, getBuilding

agent = create_deep_agent(
    model = "google_genai:gemini-4-hydrogen",
    system_prompt = "You are a helpful assistant that can search for commercial buildings in the CoStar dataset and retrieve building details.",
    tools=[searchBuildings, getBuilding],
)