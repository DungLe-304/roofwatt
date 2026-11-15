"""Agent trace: readable one-line summaries per tool, live from LangChain callbacks and saved from messages."""

import json
import uuid

from langchain_core.messages import ToolMessage

from agent.results import toolSummary
from ui.trace import LiveTrace

RANK = json.dumps({"city": "Houston", "propertyType": "Office", "totalMatches": 185, "rankedCount": 173,
	"excluded": {"errors": [], "belowMinimumSize": 12, "noPayback": 0}, "ranked": [{}] * 10})


def test_summaries_are_human_readable():
	assert toolSummary("rankBuildings", RANK) == (True, "185 office buildings in Houston screened · 173 ranked · 12 too small → top 10 kept")
	assert toolSummary("searchBuildings", "buildings=[Building(buildingId='1'), Building(buildingId='2')] totalMatches=48 warnings=[]") \
		== (True, "2 buildings found (of 48 matches)")
	assert toolSummary("getBuilding", "buildingId='240117' propertyType='Office' address='5959 Corporate Dr'") \
		== (True, "details loaded: 5959 Corporate Dr")
	assert toolSummary("write_todos", "Updated todo list", {"todos": [{}, {}]}) == (True, "planned 2 steps")
	assert toolSummary("computeFinancials", '{"simplePaybackYr": 10.934, "annualSavingsUsd": 142145.01}') \
		== (True, "payback 10.93 yr · $142,145/yr savings")
	assert toolSummary("getRoofImage", '{"buildingId": "1", "imagePath": "/x.jpg"}') == (True, "aerial roof image ready")
	assert toolSummary("getRoofImage", '{"buildingId": "1", "error": "Vexcel down"}') == (False, "error: Vexcel down")


def test_live_trace_tracks_running_and_finished_tools():
	live, first, second = LiveTrace(), uuid.uuid4(), uuid.uuid4()
	live.on_chat_model_start({}, [])
	live.on_tool_start({"name": "rankBuildings"}, "", run_id=first, inputs={"city": "Houston"})
	live.on_tool_start(None, "", run_id=second, name="getRoofImage", inputs={"buildingId": "1"})
	assert live.drain() == "Aerial image…"
	assert live.markdown() == ("1. :material/leaderboard: **Rank buildings** · _running…_\n"
		"2. :material/satellite_alt: **Aerial image** · _running…_")
	live.on_tool_end(ToolMessage(content=RANK, tool_call_id="c0"), run_id=first)
	live.on_tool_error(RuntimeError("timeout"), run_id=second)
	assert live.drain() is None
	assert live.markdown() == ("1. :material/leaderboard: **Rank buildings** · 185 office buildings in Houston screened · "
		"173 ranked · 12 too small → top 10 kept\n2. :material/error: **Aerial image** · :red[error: timeout]")
