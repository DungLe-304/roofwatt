import json
import os
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st

from agent.agent import createRoofWattAgent, fallbackModelName
from agent.results import rankingResult, roofImages, toolTrace
from agent.tools import getRoofImage
from config import loadSettings
from data.costar_client import CostarClient, getBuilding
from ui.components import (assumptionsSidebar, emptyState, header, injectCss, kpiRow, propertySearchSidebar,
	proposalPanel, queryBar, rankedCards)
from ui.detail import showDetail
from ui.proposal import splitProposal
from ui.ranking import MAP_HEIGHT_PX, addCoordinates, rankingDeck, rankingTable, selectedFromMap, summaryText
from ui.trace import LiveTrace, showTrace
from ui.whatif import recalculate

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
		with st.spinner("Placing buildings on the map…"):
			ranking = ranking | {"ranked": addCoordinates(ranking["ranked"], CostarClient().iterRecords())}
	return {"query": requestText, "response": extractText(messages[-1].content), "ranking": ranking,
		"images": [list(image) for image in roofImages(messages)], "trace": toolTrace(messages),
		"model": modelLabel(agent), "savedAt": datetime.now().strftime("%b %d, %H:%M")}


def executeRequest(agent, agentError, requestText):
	"""Run one request; on failure keep the current results, or fall back to the last saved run. True on success."""
	history = buildAgentHistory(st.session_state.chatMessages + [{"role": "user", "content": requestText}])
	try:
		if agent is None:
			raise RuntimeError(agentError or "The agent could not be started.")
		run = runAgent(agent, requestText, history)
	except Exception as error:
		message = friendlyError(error)
		saved = loadSavedRun()
		if st.session_state.run is None and saved:
			st.session_state.run = saved | {"fromCache": True}
			message += f" Showing the last saved analysis ({saved.get('savedAt', 'earlier')})."
		elif st.session_state.run is not None:
			message += " Your previous results are still shown below."
		st.session_state.notice = message
		return False
	st.session_state.chatMessages += [{"role": "user", "content": requestText}, {"role": "assistant", "content": run["response"]}]
	st.session_state.run, st.session_state.notice, st.session_state.lastMapPick = run, None, None
	st.session_state.selectedId = str(run["ranking"]["ranked"][0]["buildingId"]) if run["ranking"] else None
	saveRun(run)
	return True


def showRanking(run, ranking):
	base = ranking["ranked"]
	assumptions = st.session_state.assumptions
	rows = recalculate(base, assumptions) if assumptions else base
	if assumptions:
		st.warning("What-if assumptions from the sidebar are active: the numbers below are recalculated for these "
			f"{len(rows)} buildings (re-run the agent to re-rank every building).", icon = ":material/tune:")
	kpiRow(ranking, rows)

	ids = [str(row["buildingId"]) for row in rows]
	if st.session_state.selectedId not in ids:
		st.session_state.selectedId = ids[0]
	mapColumn, listColumn = st.columns([11, 9], gap = "large")
	with mapColumn, st.container(key = "panel-map"):
		st.markdown("#### :material/map: Where the best roofs are")
		deck = rankingDeck(rows, st.session_state.selectedId)
		if deck is None:
			st.info("No coordinates for these buildings, so the map is empty.", icon = ":material/location_off:")
		else:
			event = st.pydeck_chart(deck, height = MAP_HEIGHT_PX, on_select = "rerun", selection_mode = "single-object", key = "map")
			picked = selectedFromMap(event)
			if picked and picked != st.session_state.lastMapPick:  # a new click on the map, not a stale selection
				st.session_state.selectedId = st.session_state.lastMapPick = picked
				st.rerun()
		st.caption(f"{summaryText(ranking)} Green = best payback, red = slowest of these; dot size = system size. Click a dot or a card.")
		with st.expander("Table view", icon = ":material/table:"):
			st.dataframe(rankingTable(rows), hide_index = True, width = "stretch")
	with listColumn, st.container(key = "panel-list"):
		st.markdown(f"#### :material/leaderboard: Top {len(rows)} by payback")
		rankedCards(rows, ranking.get("propertyType", ""), st.session_state.selectedId, height = MAP_HEIGHT_PX + 40)

	row = next(row for row in rows if str(row["buildingId"]) == st.session_state.selectedId)
	baseline = next((b for b in base if str(b["buildingId"]) == st.session_state.selectedId), None) if assumptions else None
	imagePath, imageError = dict(st.session_state.run.get("images") or []).get(str(row["buildingId"])), None
	if not imagePath:
		with st.spinner("Fetching the aerial roof image…"):
			imageResult = roofImageFor(str(row["buildingId"]))
		imagePath, imageError = imageResult.get("imagePath"), imageResult.get("error")
	showDetail(row, imagePath, imageError, lookupBuilding(str(row["buildingId"])), baseline = baseline,
		assumptions = assumptions, propertyType = ranking.get("propertyType"))


def showResults(run):
	if run.get("fromCache"):
		st.info(f"Saved analysis from {run.get('savedAt', 'an earlier run')} (offline fallback).", icon = ":material/history:")
	showTrace(run.get("trace") or [], run.get("model"))
	if run.get("ranking"):
		showRanking(run, run["ranking"])
	summary, proposal = splitProposal(run.get("response", ""))
	if proposal:
		proposalPanel(proposal, "Owner proposal", "roofwatt-proposal", run.get("model"))
		if summary:
			with st.expander("Agent's full answer", icon = ":material/chat:"):
				st.markdown(summary)
	else:
		with st.container(key = "panel-answer"):
			st.markdown("<div class='rw-eyebrow'>Agent answer</div>", unsafe_allow_html = True)
			st.markdown(run.get("response") or "_The agent returned no text._")
			if run.get("model"):
				st.caption(run["model"])


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

	if st.session_state.notice:
		st.error(st.session_state.notice, icon = ":material/error:")
	if st.session_state.run is None:
		emptyState()
	else:
		showResults(st.session_state.run)

	modelStatus.caption(modelLabel(agent) if agent is not None else f"Model: unavailable · {agentError}")
