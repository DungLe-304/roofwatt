import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

import data.buildings as osm
import agent.agent as agents
from agent.results import rankingResult, roofImages, toolTrace
from agent.tools import getRoofImage
from config import loadSettings
from data.costar_client import CostarClient, getBuilding
from ui.components import (DEMO_QUERY, assumptionsForm, darkTheme, emptyState, kpiRow, letter, queryForm, rankedList,
	aiEngine, sidebar, structuredSearch)
from ui.detail import showDetail
from ui.proposal import splitProposal
from ui.ranking import MAP_HEIGHT_PX, addCoordinates, rankingDeck, rankingTable, selectedFromMap, summaryText
from ui.styles import injectCss
from ui.sunlight import queryDateFor
from ui.trace import LiveTrace, showTrace
from ui.whatif import recalculate

appRoot = Path(__file__).resolve().parent
pageIconPath = appRoot / "assets" / "roofwatt-logo-square.svg"
# Last successful run, shown if the agent fails (offline demo fallback). cache/ is gitignored; tests point this elsewhere.
lastRunPath = Path(os.environ.get("ROOFWATT_LAST_RUN") or appRoot / "cache" / "ui" / "last_run.json")
CITY_LABELS = {"Houston": "Houston, TX", "Los Angeles": "Los Angeles, CA"}

st.set_page_config(page_title = "RoofWatt", page_icon = str(pageIconPath), layout = "wide", initial_sidebar_state = "expanded",
	menu_items = {"About": "RoofWatt ranks commercial rooftops by solar payback and drafts the owner pitch. HackPrinceton Fall 2026."})
injectCss()


@st.cache_resource
def loadAgent(mode, localModel):
	"""One agent per (AI mode, local model): Cloud = Gemini with a local fallback, Local = Ollama only."""
	return agents.createAgent(mode, localModel)


@st.cache_data(ttl = 15, show_spinner = False)
def localModels():
	return agents.listLocalModels()


def chosenLocalModel():
	return st.session_state.get("localModel") or agents.fallbackModelName


def modelLabel(agent):
	"""Which LLM answers: Gemini, local Ollama (Local mode), or Ollama after the Cloud agent hit the Gemini quota."""
	if st.session_state.get("aiMode") == agents.LOCAL:
		return f"Model: Ollama · {chosenLocalModel()} (local)"
	if getattr(agent, "useLocalModel", False):
		return f"Model: Ollama · {chosenLocalModel()} (local fallback, Gemini quota exhausted)"
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


FOOTPRINT_RETRY_S = 300  # a failed download (Overpass rate limit, timeout) is retried after this long


@st.cache_resource
def footprintStore():
	return {}  # positions -> {"result": geometry or None while downloading, "at": epoch seconds}


def footprints(positions):
	"""Nearby OSM footprints for the 2D map without blocking the page.

	Returns the geometry, or None while a worker thread downloads it (data/buildings.py caches successes on disk,
	so later sessions get them at once). The public Overpass API can take 20 s or answer 429.
	"""
	store = footprintStore()
	entry = store.get(positions)
	failed = entry and entry["result"] is not None and not entry["result"]["buildings"] and entry["result"]["warning"]
	if entry is None or (failed and time.time() - entry["at"] > FOOTPRINT_RETRY_S):
		entry = store[positions] = {"result": None, "at": time.time()}

		def work():
			entry["result"], entry["at"] = osm.loadBuildingGeometry(positions), time.time()

		worker = threading.Thread(target = work, daemon = True)
		worker.start()
		worker.join(0.3)  # a disk-cache hit finishes within this, so the buildings are there on first paint
	return entry["result"]


@st.fragment(run_every = 2)
def redrawWhenFootprintsArrive(positions):
	"""Polls while the download runs; one full rerun draws the footprints (or the notice that there are none)."""
	entry = footprintStore().get(positions)
	if entry and entry["result"] is not None:
		st.rerun()


def friendlyError(error):
	text = str(error)
	if "429" in text or "RESOURCE_EXHAUSTED" in text:
		return "Gemini's free quota is used up and the local model did not answer. Try again after the quota resets."
	if "ollama" in text.lower() or "Connection refused" in text or "ConnectError" in type(error).__name__:
		return f"The local model ({chosenLocalModel()}) did not answer: Ollama is not running, or the model is not pulled."
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
	"""Invoke the agent on a worker thread and list its tool calls live; returns the run to keep in session state."""
	live, outcome, submittedAt = LiveTrace(), {}, datetime.now(timezone.utc).isoformat()

	def work():
		try:
			outcome["result"] = agent.invoke({"messages": history}, config = {"callbacks": [live]})
		except Exception as error:  # re-raised on the Streamlit thread below
			outcome["error"] = error

	worker = threading.Thread(target = work, daemon = True)
	worker.start()
	with st.status("Planning the analysis", expanded = True) as status:
		steps = st.empty()
		while worker.is_alive():
			label = live.drain()
			if label:
				status.update(label = label)
			steps.markdown(live.markdown() or "Reading the request and planning tool calls.")
			worker.join(0.2)
		live.drain()
		if "error" in outcome:
			status.update(label = "The agent hit a problem", state = "error", expanded = False)
			raise outcome["error"]
		status.update(label = "Analysis complete", state = "complete", expanded = False)

	messages = outcome["result"]["messages"]
	ranking = rankingResult(messages)
	if ranking:
		with st.spinner("Placing buildings on the map"):
			ranking = ranking | {"ranked": addCoordinates(ranking["ranked"], CostarClient().iterRecords()),
				"queryDate": queryDateFor(ranking["city"], submittedAt)}
	return {"query": requestText, "response": extractText(messages[-1].content), "ranking": ranking,
		"images": [list(image) for image in roofImages(messages)], "trace": toolTrace(messages),
		"model": modelLabel(agent), "savedAt": datetime.now().strftime("%b %d, %H:%M")}


def executeRequest(agent, agentError, requestText):
	"""Run one request; on failure keep the current results, or fall back to the last saved run. True on success."""
	history = buildAgentHistory(st.session_state.chatMessages + [{"role": "user", "content": requestText}])
	st.session_state.lastQuery = requestText
	try:
		if agent is None:
			raise RuntimeError(agentError or "The agent could not be started.")
		run = runAgent(agent, requestText, history)
	except Exception as error:
		message = friendlyError(error)
		saved = loadSavedRun()
		if st.session_state.run is None and saved:
			st.session_state.run = saved | {"fromCache": True}
			message += f" The last saved analysis ({saved.get('savedAt', 'earlier')}) is on the Results page."
		elif st.session_state.run is not None:
			message += " Your previous results are unchanged."
		st.session_state.notice = message
		return False
	st.session_state.chatMessages += [{"role": "user", "content": requestText}, {"role": "assistant", "content": run["response"]}]
	st.session_state.run, st.session_state.notice, st.session_state.lastMapPick = run, None, None
	st.session_state.selectedId = str(run["ranking"]["ranked"][0]["buildingId"]) if run["ranking"] else None
	st.session_state.pop("mapFocus", None)
	saveRun(run)
	return True


def currentRanking():
	"""(ranking, sourced rows, rows under the active what-if assumptions) for the run in session state."""
	ranking = (st.session_state.run or {}).get("ranking")
	if not ranking:
		return None, [], []
	base = ranking["ranked"]
	rows = recalculate(base, st.session_state.assumptions) if st.session_state.assumptions else base
	ids = [str(row["buildingId"]) for row in rows]
	if st.session_state.selectedId not in ids:
		st.session_state.selectedId = ids[0]
	return ranking, base, rows


def whatIfNotice(count):
	if st.session_state.assumptions:
		st.info(f"What-if assumptions are active: numbers are recalculated for these {count} buildings. "
			"Re-run the analysis to re-rank every building.")


def openBuilding(buildingId):
	st.session_state.selectedId, st.session_state.openBuilding = buildingId, True


def analyzePage():
	st.title("Analyze")
	st.markdown("<p class='rw-lede'>Rank Houston commercial rooftops by solar payback, then draft the pitch for the "
		"best one.</p>", unsafe_allow_html = True)
	query, runClicked = queryForm(st.session_state.get("lastQuery") or DEMO_QUERY, disabled = bool(ENGINE_PROBLEM))
	if ENGINE_PROBLEM:
		st.caption(f"{ENGINE_PROBLEM} Change the AI engine in the sidebar.")
	searchSubmitted, filters = structuredSearch(disabled = bool(ENGINE_PROBLEM))

	request = None
	if searchSubmitted:
		request = buildSearchPrompt(filters["city"], filters["propertyType"], filters["minGrossArea"], filters["limit"],
			filters["randomize"], filters["mode"])
	elif runClicked and query:
		request = query
	if request:
		succeeded = executeRequest(AGENT, AGENT_ERROR, request)
		if st.session_state.aiMode == agents.CLOUD and getattr(AGENT, "useLocalModel", False):
			# Gemini quota ran out during this run: flip the switch to Local (applied before the sidebar redraws)
			st.session_state.switchToLocal = True
		if succeeded:
			st.switch_page(PAGES["results"])
		elif st.session_state.get("switchToLocal"):
			st.rerun()

	if st.session_state.notice:
		st.error(st.session_state.notice)
	run = st.session_state.run
	if run:
		showTrace(run.get("trace") or [], run.get("model"))
		st.page_link(PAGES["results"], label = "View results")


def resultsPage():
	if st.session_state.pop("openBuilding", False):
		st.switch_page(PAGES["building"])
	st.title("Results")
	run = st.session_state.run
	if not run:
		return emptyState(PAGES["analyze"])
	if run.get("fromCache"):
		st.info(f"Saved analysis from {run.get('savedAt', 'an earlier run')}, shown because the agent could not answer.")
	ranking, _, rows = currentRanking()
	if not ranking:
		st.markdown("This run did not rank buildings. The agent's answer:")
		st.markdown(run.get("response") or "The agent returned no text.")
		return
	whatIfNotice(len(rows))
	kpiRow(ranking, rows)

	located = [row for row in rows if row.get("lat") is not None and row.get("lon") is not None]
	names = {str(row["buildingId"]): row.get("address") or f"Building {row['buildingId']}" for row in located}
	mapColumn, listColumn = st.columns([11, 9], gap = "large")
	with listColumn:  # drawn first: the map below may wait on the footprint download
		st.markdown(f"<p class='rw-label'>Top {len(rows)} by payback</p>", unsafe_allow_html = True)
		rankedList(rows, st.session_state.selectedId, MAP_HEIGHT_PX + 250, openBuilding)
	with mapColumn:
		positions = tuple((row["lon"], row["lat"]) for row in located)
		geometry = footprints(positions)
		buildings = geometry["buildings"] if geometry else []
		focusId = st.selectbox("Map view", [None] + list(names), key = "mapFocus",
			format_func = lambda buildingId: "All results" if buildingId is None else names[buildingId])
		focusRow = next((row for row in located if str(row["buildingId"]) == focusId), None)
		deck = rankingDeck(rows, st.session_state.selectedId, dark = darkTheme(), buildings = buildings, focusRow = focusRow)
		if deck is None:
			st.info("No coordinates for these buildings, so there is no map.")
		else:
			event = st.pydeck_chart(deck, height = MAP_HEIGHT_PX, on_select = "rerun", selection_mode = "single-object", key = "map")
			picked = selectedFromMap(event)
			if picked and picked != st.session_state.lastMapPick:  # a new click on the map, not a stale selection
				st.session_state.selectedId = st.session_state.lastMapPick = picked
				st.rerun()
			st.caption(f"{summaryText(ranking)} Green is the best payback; red is the lowest; dot size is system size.")
			notes = []
			if geometry is None:
				notes.append("Loading building footprints from OpenStreetMap.")
			elif buildings:
				notes.append(f"Buildings: © OpenStreetMap contributors (ODbL), {len(buildings)} flat footprints; not CoStar "
					"property boundaries.")
			elif geometry["warning"].startswith("Building geometry unavailable"):
				notes.append("Building footprints are unavailable right now (OpenStreetMap did not answer), so the "
					"map shows the ranked points only.")
			elif geometry["warning"]:
				notes.append(geometry["warning"])
			if notes:
				st.caption(" ".join(notes))
		if geometry is None:
			redrawWhenFootprintsArrive(positions)
	with st.expander("Table"):
		st.dataframe(rankingTable(rows), hide_index = True, width = "stretch")


def pickBuilding():
	st.session_state.selectedId = st.session_state.buildingPicker


def buildingPage():
	st.title("Building")
	ranking, base, rows = currentRanking()
	if not ranking:
		return emptyState(PAGES["analyze"])
	whatIfNotice(len(rows))
	byId = {str(row["buildingId"]): row for row in rows}
	selectedId = st.selectbox("Building", list(byId), index = list(byId).index(st.session_state.selectedId), key = "buildingPicker",
		on_change = pickBuilding, format_func = lambda buildingId: f"#{byId[buildingId]['rank']} · "
		f"{byId[buildingId].get('address') or 'Building ' + buildingId}")
	row = byId[selectedId]
	baseline = next((b for b in base if str(b["buildingId"]) == selectedId), None) if st.session_state.assumptions else None
	imagePath, imageError = dict(st.session_state.run.get("images") or []).get(selectedId), None
	if not imagePath:
		with st.spinner("Fetching the aerial roof image"):
			imageResult = roofImageFor(selectedId)
		imagePath, imageError = imageResult.get("imagePath"), imageResult.get("error")
	showDetail(row, imagePath, imageError, lookupBuilding(selectedId), baseline = baseline,
		assumptions = st.session_state.assumptions, propertyType = ranking.get("propertyType"))


def proposalPage():
	st.title("Proposal")
	run = st.session_state.run
	if not run:
		return emptyState(PAGES["analyze"])
	summary, proposal = splitProposal(run.get("response", ""))
	if proposal:
		letter(proposal, "roofwatt-proposal", run.get("model"))
		if summary:
			with st.expander("Rest of the agent's answer"):
				st.markdown(summary)
	else:
		st.markdown("The agent did not draft a letter in this run. Its answer:")
		st.markdown(run.get("response") or "The agent returned no text.")


def assumptionsPage():
	st.title("Assumptions")
	st.markdown("<p class='rw-lede'>What-if values recalculate the buildings already shown. They do not re-run the agent "
		"or re-rank every building.</p>", unsafe_allow_html = True)
	assumptionsForm()
	if st.session_state.assumptions:
		st.markdown("What-if values are active on Results and Building.")
		if st.button("Reset to sourced defaults"):
			st.session_state.assumptions = None
			st.rerun()
	else:
		st.markdown("Using the sourced defaults from config.py.")
	if st.session_state.run:
		st.page_link(PAGES["results"], label = "View results")


if __name__ == "__main__":
	for name, default in {"run": None, "chatMessages": [], "selectedId": None, "assumptions": None, "notice": None,
			"lastMapPick": None, "aiMode": agents.CLOUD}.items():
		st.session_state.setdefault(name, default)
	if st.session_state.pop("switchToLocal", False):
		st.session_state.aiMode = st.session_state.lastMode = agents.LOCAL  # automatic switch, not the viewer's pick
		st.session_state.fallbackNote = "Switched from Cloud: the Gemini free quota is used up."
	mode = st.session_state.aiMode
	retryGemini = False
	if mode != st.session_state.get("lastMode"):
		if st.session_state.get("lastMode") is not None:
			st.session_state.fallbackNote = None  # the viewer picked a mode: drop the automatic-switch note
			retryGemini = mode == agents.CLOUD
		st.session_state.lastMode = mode

	PAGES = {
		"analyze": st.Page(analyzePage, title = "Analyze", icon = ":material/search:", url_path = "analyze", default = True),
		"results": st.Page(resultsPage, title = "Results", icon = ":material/leaderboard:", url_path = "results"),
		"building": st.Page(buildingPage, title = "Building", icon = ":material/apartment:", url_path = "building"),
		"proposal": st.Page(proposalPage, title = "Proposal", icon = ":material/description:", url_path = "proposal"),
		"assumptions": st.Page(assumptionsPage, title = "Assumptions", icon = ":material/tune:", url_path = "assumptions"),
	}
	page = st.navigation(list(PAGES.values()), position = "hidden")
	city = ((st.session_state.run or {}).get("ranking") or {}).get("city")
	def engine():
		names, problem = localModels() if st.session_state.aiMode == agents.LOCAL else ([], None)
		return aiEngine(names, problem, agents.hasGeminiKey(), agents.fallbackModelName)

	with st.sidebar:
		modelSlot, ENGINE_PROBLEM = sidebar(PAGES, CITY_LABELS.get(city, "Houston, TX"), engine)

	try:
		AGENT, AGENT_ERROR = (None, ENGINE_PROBLEM) if ENGINE_PROBLEM else (loadAgent(mode, chosenLocalModel()), None)
	except Exception as error:
		AGENT, AGENT_ERROR = None, friendlyError(error)
	if retryGemini and AGENT is not None:
		AGENT.useLocalModel = False  # choosing Cloud again retries Gemini after an earlier quota fallback

	def showModel():
		modelSlot.markdown(modelLabel(AGENT) if AGENT is not None else f"Model: unavailable · {AGENT_ERROR}")

	showModel()
	page.run()
	showModel()  # again after the page ran: a quota error during the run switches the model to Ollama
