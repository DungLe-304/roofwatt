import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit.components.v1 as components
import streamlit as st
import streamlit_hotkeys as hotkeys

from agent.agent import createRoofWattAgent, fallbackModelName
from agent.results import rankingResult, roofImages, toolTrace
from agent.tools import getRoofImage
from config import loadSettings
from data.costar_client import CostarClient, getBuilding
from ui.detail import selectedIndex, showDetail
from ui.ranking import addCoordinates, showRanking
from ui.trace import showTrace
from ui.sunlight import queryDateFor

appRoot = Path(__file__).resolve().parent
pageIconPath = appRoot / "assets" / "roofwatt-logo-square.svg"

st.set_page_config(page_title = "RoofWatt", page_icon = str(pageIconPath), layout = "wide", initial_sidebar_state = "expanded")

with st.sidebar:
	with st.form("propertyFilters"):
		st.header("Property filters")
		city = st.selectbox("City", ["Houston", "Los Angeles"], index = 0)
		propertyType = st.selectbox("Property type", ["Office", "Industrial", "GeneralRetail", "Flex", "Multifamily", "Hospitality"], index = 0)
		minGrossArea = st.number_input("Minimum gross area (sq ft)", min_value = 0, value = 10000, step = 1000)
		limit = st.number_input("Number of properties", min_value = 1, max_value = 20, value = 10, step = 1)
		mode = st.radio("Mode", ["Search", "Rank"], index = 0, help = "Search mode finds properties that meet the criteria, while Rank mode ranks the properties by solar potential.")
		randomize = st.checkbox("Randomize search results", value = False, disabled = mode == "Rank")
		runSearch = st.form_submit_button("Search properties")

hotkeys.activate([hotkeys.hk("scroll_bottom", "End", ctrl = True, prevent_default = True, help = "Scroll to the latest message")])

st.title("RoofWatt")
st.caption("A commercial solar analysis agent for properties in Houston and Los Angeles.")

@st.cache_resource
def loadAgent(checkGemini = True):
	return createRoofWattAgent(pingGemini = checkGemini)

def modelLabel(agent):
	"""Which LLM the agent uses now: Gemini, or local Ollama once QuotaFallbackAgent has switched."""
	if getattr(agent, "useLocalModel", False):
		return f"Model: Ollama · {fallbackModelName} (local fallback, Gemini quota exhausted)"
	return f"Model: Gemini · {loadSettings().modelName.split(':', 1)[-1]}"

def extractText(content):
	if isinstance(content, str):
		return content
	if isinstance(content, list):
		textParts = []
		for block in content:
			if isinstance(block, dict) and block.get("type") == "text":
				textParts.append(block.get("text", ""))

		return "\n".join(textParts)
	elif isinstance(content, dict):
		return "\n".join([f"{key}: {extractText(value)}" for key, value in content.items()])
	else:
		return str(content)

def buildAgentHistory(messages):
	settings = loadSettings()
	remainingCharacters = settings.agentContextCharacters
	boundedHistory = []

	for message in reversed(messages[-settings.agentContextMessages:]):
		content = str(message.get("content", ""))
		if not content or remainingCharacters <= 0:
			continue

		if len(content) > remainingCharacters:
			truncationNotice = "\n[Earlier content truncated]"
			if remainingCharacters > len(truncationNotice):
				content = content[:remainingCharacters - len(truncationNotice)] + truncationNotice
			else:
				content = content[:remainingCharacters]

		boundedHistory.append({"role": message["role"], "content": content})
		remainingCharacters -= len(content)

	return list(reversed(boundedHistory))

def scrollToBottom():
	componentKey = time.time_ns()

	jsCode = f"""
	<script>
		const componentKey = "{componentKey}";

		const scrollToBottom = () => {{if (window.frameElement) {{window.frameElement.scrollIntoView({{behavior: "smooth", block: "end"}});}}}};

		window.requestAnimationFrame(() => {{window.setTimeout(scrollToBottom, 150);}});
	</script>
	"""

	components.html(jsCode, height=0)

hotkeys.on_pressed("scroll_bottom", scrollToBottom)

if st.button("Scroll to latest message"):
	scrollToBottom()


def showRoofImages(images):
	for buildingId, imagePath in images:
		st.image(imagePath, caption = f"Aerial roof image, building {buildingId} (Vexcel Imaging)", width = 480)


@st.cache_data(ttl = 300, show_spinner = False)
def roofImageFor(buildingId):
	"""getRoofImage, memoized so reruns (every click) do not refetch or retry a failing Vexcel call (60 s timeout)."""
	return getRoofImage(buildingId)


@st.cache_data(show_spinner = False)
def lookupBuilding(buildingId):
	try:
		return getBuilding(buildingId)
	except (LookupError, ValueError):
		return None


def showAssistantExtras(message, key):
	"""Tool trace, ranked map/table, detail panel for the selected row, then any other roof images."""
	if message.get("trace"):
		showTrace(message["trace"])
	images = message.get("images", [])
	ranking = message.get("ranking")
	if ranking:
		rows = ranking["ranked"]
		row = rows[selectedIndex(showRanking(ranking, key = key), len(rows))]
		imagePath, imageError = dict(images).get(row["buildingId"]), None
		if not imagePath:
			imageResult = roofImageFor(row["buildingId"])
			imagePath, imageError = imageResult.get("imagePath"), imageResult.get("error")
		showDetail(row, imagePath, imageError, lookupBuilding(row["buildingId"]))
		rankedIds = {ranked["buildingId"] for ranked in rows}
		images = [image for image in images if image[0] not in rankedIds]  # already shown in the detail panel
	showRoofImages(images)

def buildSearchPrompt(city, propertyType, minGrossArea, limit, randomize, mode):
	filters = f"city={city}, propertyType={propertyType}, minimum gross area={minGrossArea} sq ft, limit={limit}"
	if mode == "Search":
		randomInstruction = "randomize=true" if randomize else "randomize=false"
		return f"Use searchBuildings with {filters}, {randomInstruction}. Report returned facts and warnings. Do not rank these results."
	if mode == "Rank":
		return f"Use rankBuildings once with {filters}. Rank matching buildings by returned simple payback. Do not randomize or call computeFinancials one building at a time. Report exclusions and assumptions concisely."
	raise ValueError("Mode must be Search or Rank.")


def runAgentRequest(agent, requestText):
	submittedAt = datetime.now(timezone.utc).isoformat()
	st.session_state.chatMessages.append({"role": "user", "content": requestText})
	with st.chat_message("user"):
		st.markdown(requestText)

	with st.chat_message("assistant"):
		with st.spinner("Analyzing properties..."):
			try:
				history = buildAgentHistory(st.session_state.chatMessages)
				result = agent.invoke({"messages": history})
				responseText = extractText(result["messages"][-1].content)
				images = roofImages(result["messages"])
				ranking = rankingResult(result["messages"])
				trace = toolTrace(result["messages"])
				if ranking:
					ranking = ranking | {"ranked": addCoordinates(ranking["ranked"], CostarClient().iterRecords()), "queryDate": queryDateFor(ranking["city"], submittedAt)}
				model = modelLabel(agent)  # read after invoke: a quota error during this request switches to Ollama
				st.markdown(responseText)
				st.caption(model)
				showAssistantExtras({"images": images, "ranking": ranking, "trace": trace}, key = f"ranking-current-{len(st.session_state.chatMessages)}")
				st.session_state.chatMessages.append({"role": "assistant", "content": responseText, "images": images, "ranking": ranking, "trace": trace, "model": model})
			except Exception as error:
				errorMessage = str(error)
				if "429" in errorMessage or "RESOURCE_EXHAUSTED" in errorMessage:
					st.error("Gemini quota is currently exhausted. Wait for the quota window to reset, then try again.")
				else:
					st.error(f"RoofWatt could not complete the request: {errorMessage}")

	scrollToBottom()

if __name__ == "__main__":
	agent = loadAgent()

	if "chatMessages" not in st.session_state:
		st.session_state.chatMessages = []

	if st.sidebar.button("Clear conversation"):
		st.session_state.chatMessages = []
		st.rerun()
	modelStatus = st.sidebar.empty()  # filled last, so it reflects a switch to Ollama during this run

	for index, message in enumerate(st.session_state.chatMessages):
		with st.chat_message(message["role"]):
			st.markdown(message["content"])
			if message.get("model"):
				st.caption(message["model"])
			if message["role"] == "assistant":
				showAssistantExtras(message, key = f"ranking-{index}")

	userPrompt = st.chat_input("Ask RoofWatt to find commercial properties")

	if runSearch:
		runAgentRequest(agent, buildSearchPrompt(city, propertyType, minGrossArea, int(limit), randomize, mode))
	elif userPrompt:
		runAgentRequest(agent, userPrompt)

	modelStatus.caption(modelLabel(agent))
