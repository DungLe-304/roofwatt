import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

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
# Last successful run, shown if the agent fails (offline demo fallback). cache/ is gitignored; tests point this elsewhere.
lastRunPath = Path(os.environ.get("ROOFWATT_LAST_RUN") or appRoot / "cache" / "ui" / "last_run.json")

st.set_page_config(page_title = "RoofWatt", page_icon = str(pageIconPath), layout = "wide", initial_sidebar_state = "collapsed")
injectCss()


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

def buildSearchPrompt(city, propertyType, minGrossArea, limit, randomize, mode):
	filters = f"city={city}, propertyType={propertyType}, minimum gross area={minGrossArea} sq ft, limit={limit}"
	if mode == "Search":
		randomInstruction = "randomize=true" if randomize else "randomize=false"
		return f"Use searchBuildings with {filters}, {randomInstruction}. Report returned facts and warnings. Do not rank these results."
	if mode == "Rank":
		return f"Use rankBuildings once with {filters}. Rank matching buildings by returned simple payback. Do not randomize or call computeFinancials one building at a time. Report exclusions and assumptions concisely."
	raise ValueError("Mode must be Search or Rank.")


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


def friendlyError(error):
	text = str(error)
	if "429" in text or "RESOURCE_EXHAUSTED" in text:
		return "Gemini's free quota is used up and the local backup model did not answer. Try again after the quota resets."
	if "ollama" in text.lower() or "Connection refused" in text or "ConnectError" in type(error).__name__:
		return "The local backup model (Ollama) is not running on this machine, so the agent could not answer."
	return f"The agent could not finish this request: {text[:240]}"


def saveRun(run):
	try:
		lastRunPath.parent.mkdir(parents = True, exist_ok = True)
		lastRunPath.write_text(json.dumps(run, default = str))
	except OSError:
		pass  # the fallback copy is optional


def loadSavedRun():
	try:
		return json.loads(lastRunPath.read_text())
	except (OSError, ValueError):
		return None


def runAgent(agent, requestText, history):
	"""Invoke the agent on a worker thread and draw its tool calls live; returns the run to keep in session state."""
	live, outcome = LiveTrace(), {}

	def work():
		try:
			outcome["result"] = agent.invoke({"messages": history}, config = {"callbacks": [live]})
		except Exception as error:  # re-raised on the Streamlit thread below
			outcome["error"] = error

	worker = threading.Thread(target = work, daemon = True)
	worker.start()
	with st.status("Planning the analysis…", expanded = True) as status:
		steps = st.empty()
		while worker.is_alive():
			label = live.drain()
			if label:
				status.update(label = label)
			steps.markdown(live.markdown() or "_Reading the request and planning tool calls…_")
			worker.join(0.2)
		live.drain()
		if "error" in outcome:
			status.update(label = "The agent hit a problem", state = "error", expanded = False)
			raise outcome["error"]
		status.update(label = "Analysis complete", state = "complete", expanded = False)

	messages = outcome["result"]["messages"]
	ranking = rankingResult(messages)
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
	for name, default in {"run": None, "chatMessages": [], "selectedId": None, "assumptions": None, "notice": None,
			"lastMapPick": None}.items():
		st.session_state.setdefault(name, default)

	try:
		agent, agentError = loadAgent(), None
	except Exception as error:
		agent, agentError = None, friendlyError(error)

	with st.sidebar:
		assumptionsSidebar()
		st.divider()
		searchSubmitted, filters = propertySearchSidebar()
		if st.button("Clear results", icon = ":material/delete_sweep:", width = "stretch"):
			for name in ("run", "selectedId", "notice", "lastMapPick"):
				st.session_state[name] = None
			st.session_state.chatMessages = []
			st.rerun()
		modelStatus = st.empty()  # filled last, so it reflects a switch to Ollama during this run

	ranking = (st.session_state.run or {}).get("ranking") or {}
	header({"Houston": "Houston, TX", "Los Angeles": "Los Angeles, CA"}.get(ranking.get("city"), "Houston, TX"))
	query, runClicked = queryBar()

	request = None
	if searchSubmitted:
		request = buildSearchPrompt(filters["city"], filters["propertyType"], filters["minGrossArea"], filters["limit"],
			filters["randomize"], filters["mode"])
	elif runClicked and query:
		request = query
	if request and executeRequest(agent, agentError, request):
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
