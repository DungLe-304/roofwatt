import time
from pathlib import Path

import streamlit.components.v1 as components
import streamlit as st
import streamlit_hotkeys as hotkeys

from agent.agent import createRoofWattAgent
from agent.results import rankingResult, roofImages, toolTrace
from agent.tools import getRoofImage
from config import loadSettings
from data.costar_client import CostarClient, getBuilding
from ui.detail import selectedIndex, showDetail
from ui.ranking import addCoordinates, showRanking
from ui.trace import showTrace

appRoot = Path(__file__).resolve().parent
pageIconPath = appRoot / "assets" / "roofwatt-logo-square.svg"

st.set_page_config(page_title = "RoofWatt", page_icon = str(pageIconPath), layout = "wide", initial_sidebar_state = "expanded")

with st.sidebar:
	with st.form("propertyFilters"):
		st.header("Property filters")
		runSearch = st.form_submit_button("Search properties")
		city = st.selectbox("City", ["Houston", "Los Angeles"], index = 0)
		propertyType = st.selectbox("Property type", ["Office", "Retail", "Warehouse"], index = 0)
		minGrossArea = st.number_input("Minimum gross area (sq ft)", min_value = 0, value = 10000, step = 1000)	
		limit = st.number_input("Number of properties to display", min_value = 1, value = 10, step = 1)
		randomize = st.checkbox("Randomize property selection", value = True)
		mode = st.radio("Mode", ["Search", "Rank"], index = 0, help = "Search mode finds properties that meet the criteria, while Rank mode ranks the properties by solar potential.")

hotkeys.activate([hotkeys.hk("scroll_bottom", "End", ctrl = True, prevent_default = True, help = "Scroll to the latest message")])

st.title("RoofWatt")
st.caption("A commercial solar analysis agent for properties in Houston and Los Angeles.")

@st.cache_resource
def loadAgent():
	return createRoofWattAgent()

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

def buildSearchPrompt(city, propertyType, minGrossArea, limit, randomize, mode):
	if mode not in ["Search", "Rank"]:
		raise ValueError("Invalid mode. Must be 'Search' or 'Rank'.")
	if mode == "Search":
		prompt = f"Find {limit} commercial properties in {city} that are {propertyType.lower()} buildings with a minimum gross area of {minGrossArea} square feet. "
		if randomize:
			prompt += "Randomize the selection of properties. "
		if mode == "Rank":
			prompt += "Rank the properties by solar potential. "

		prompt += "Provide the results in a structured format with building ID, address, and any relevant details. Include aerial roof images for each property."

	return prompt
	

def rankingPrompt(city, propertyType, minGrossArea, limit, randomize):
	prompt = f"Rank {limit} commercial properties in {city} that are {propertyType.lower()} buildings with a minimum gross area of {minGrossArea} square feet by solar potential. "
	if randomize:
		prompt += "Randomize the selection of properties. "

	prompt += "Provide the results in a structured format with building ID, address, and any relevant details. Include aerial roof images for each property."

	return prompt

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

if __name__ == "__main__":
	agent = loadAgent()

	if "chatMessages" not in st.session_state:
		st.session_state.chatMessages = []

	for index, message in enumerate(st.session_state.chatMessages):
		with st.chat_message(message["role"]):
			st.markdown(message["content"])
			showAssistantExtras(message, key = f"ranking-{index}")

	userPrompt = st.chat_input("Ask RoofWatt to find commercial properties")

	if userPrompt:
		st.session_state.chatMessages.append({"role": "user", "content": userPrompt})

		with st.chat_message("user"):
			st.markdown(userPrompt)

		scrollToBottom()

		with st.chat_message("assistant"):
			with st.spinner("Analyzing properties..."):
				try:
					history = buildAgentHistory(st.session_state.chatMessages)
					result = agent.invoke({"messages": history})

					responseText = extractText(result["messages"][-1].content)
					ranking = rankingResult(result["messages"])
					if ranking:
						ranking = ranking | {"ranked": addCoordinates(ranking["ranked"], CostarClient().iterRecords())}
					reply = {"role": "assistant", "content": responseText, "images": roofImages(result["messages"]),
						"ranking": ranking, "trace": toolTrace(result["messages"])}
					st.markdown(responseText)
					showAssistantExtras(reply, key = f"ranking-{len(st.session_state.chatMessages)}")  # = its index once appended

					st.session_state.chatMessages.append(reply)
				except Exception as error:
					errorMessage = str(error)
					if "429" in errorMessage or "RESOURCE_EXHAUSTED" in errorMessage:
						st.error("Gemini quota is currently exhausted. Wait for the quota window to reset, then try again. RoofWatt now sends one bounded request per question.")
					else:
						st.error(f"RoofWatt could not complete the request: {errorMessage}")
					scrollToBottom()