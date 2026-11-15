"""Streamlit app with fake agents (no LLM, no network): the five pages, run flow, what-if, fallback, AI modes."""

import json

import pytest
import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage
from streamlit.testing.v1 import AppTest

import agent.agent
import data.buildings

ROW_1 = {"rank": 1, "address": "5959 Corporate Dr", "buildingId": "240117", "usableRoofM2": 7906.04,
	"systemKw": 1167.72, "annualKwh": 1660572.5, "annualSavingsUsd": 142145.01, "costPerWattUsd": 1.9,
	"capexUsd": 2218672.19, "netCapexUsd": 1553070.53, "simplePaybackYr": 10.93, "co2TonsPerYear": 552.76}
ROW_2 = {"rank": 2, "address": "Second Building", "buildingId": "999999999", "usableRoofM2": 1000.0, "systemKw": 147.7,
	"annualKwh": 207000.0, "annualSavingsUsd": 17719.2, "costPerWattUsd": 2.6, "capexUsd": 384020.0,
	"netCapexUsd": 268814.0, "simplePaybackYr": 15.17, "co2TonsPerYear": 68.91}
RANKING = {"city": "Houston", "propertyType": "Office", "totalMatches": 185, "rankedCount": 173,
	"excluded": {"errors": [], "belowMinimumSize": 12, "noPayback": 0},
	"assumptions": {"usableFactor": 0.6, "minSystemKw": 50}, "ranked": [ROW_1, ROW_2]}
REPLY = "Top 2 offices ranked by payback.\n\n## Pitch for 5959 Corporate Dr\nDear owner,\nYour roof could save $142,145/yr."


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
	"""Fresh caches per test; no Overpass call; the last-run fallback file goes to tmp_path, not the demo cache."""
	st.cache_resource.clear()
	st.cache_data.clear()
	monkeypatch.setenv("ROOFWATT_LAST_RUN", str(tmp_path / "last_run.json"))
	monkeypatch.setattr(data.buildings, "loadBuildingGeometry", lambda positions: {"buildings": [], "warning": ""})
	monkeypatch.setattr(agent.agent, "hasGeminiKey", lambda: True)
	monkeypatch.setattr(agent.agent, "listLocalModels", lambda: (["llama3.2:3b", "qwen3.5:4b"], None))


def roof_png(tmp_path):
	image = tmp_path / "roof.png"
	image.write_bytes(bytes.fromhex(
		"89504e470d0a1a0a0000000d4948445200000001000000010806000000"
		"1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"))
	return image


class FakeAgent:
	def __init__(self, image_path=None, error=None):
		self.image_path, self.error = image_path, error
		self.received = []
		self.useLocalModel = False  # QuotaFallbackAgent flag: True once Gemini quota is exhausted

	def invoke(self, state, config=None):
		self.received.append(state["messages"])
		if self.error:
			raise self.error
		return {"messages": [
			AIMessage("", tool_calls=[{"name": "rankBuildings", "args": {"city": "Houston"}, "id": "c0"},
				{"name": "getRoofImage", "args": {"buildingId": "240117"}, "id": "c1"}]),
			ToolMessage(content=json.dumps(RANKING), name="rankBuildings", tool_call_id="c0"),
			ToolMessage(content=json.dumps({"buildingId": "240117", "imagePath": str(self.image_path)}), name="getRoofImage",
				tool_call_id="c1"),
			AIMessage(REPLY),
		]}


def start(monkeypatch, fake, calls=None):
	"""Run the app with `fake` as the agent for every AI mode; `calls` records (mode, local model) per agent built."""
	def factory(mode, localModelName=None):
		if calls is not None:
			calls.append((mode, localModelName))
		return fake
	monkeypatch.setattr(agent.agent, "createAgent", factory)
	return AppTest.from_file("../app.py", default_timeout=30).run()


def goto(at, url_path):
	"""Open a st.navigation page by url_path. AppTest.switch_page only takes script files, and these pages are
	functions, so this sets the page hash AppTest itself keeps for registered pages."""
	target = "" if url_path == "analyze" else url_path  # the default page is registered with an empty path
	at._page_hash = next(page_hash for page_hash, info in at._registered_pages.items() if info.get("url_pathname") == target)
	return at.run()


def button(at, label):
	return next(b for b in at.button if b.label == label)


def title(at):
	return at.title[0].value


def text(at):
	return "\n".join(m.value for m in at.markdown)


def values(at):
	"""The value cells of the Building page's key-value list, in display order."""
	return [m.value for m in at.markdown if m.value.startswith("<div class='rw-kv-value'>")]


def test_starts_on_analyze_with_the_demo_query_and_five_nav_links(monkeypatch):
	at = start(monkeypatch, FakeAgent())
	assert not at.exception and title(at) == "Analyze"
	assert at.text_area(key="query").value.startswith("Find the 10 office buildings in Houston")
	assert len(at.sidebar.get("page_link")) == 5
	assert "Houston, TX" in [m.value for m in at.sidebar.markdown]
	for page in ("results", "building", "proposal"):
		goto(at, page)
		assert not at.exception and "No analysis yet." in text(at) and not at.metric


def test_run_opens_results_then_building_and_proposal(monkeypatch, tmp_path):
	fake = FakeAgent(roof_png(tmp_path))
	at = start(monkeypatch, fake)
	button(at, "Run analysis").click().run()
	assert not at.exception and not at.error and title(at) == "Results"
	assert fake.received[0][-1]["content"].startswith("Find the 10 office buildings")
	assert {m.label: m.value for m in at.metric} == {"Buildings analyzed": "185", "Capacity, top 2": "1,315 kW",
		"Savings/yr, top 2": "$159,864", "CO₂ avoided, top 2": "622 t/yr"}
	assert len(at.get("deck_gl_json_chart")) == 1
	rows = [m.value for m in at.markdown if m.value.startswith("<div class='rw-row'>")]
	assert len(rows) == 2 and "rw-dot" in rows[0] and "rw-dot" not in rows[1]  # only #1 carries the orange dot
	assert "<b>10.93 yr</b> payback" in rows[0] and "<b>$142,145</b>/yr" in rows[0]

	at.button(key="view-999999999").click().run()  # View on the second row opens its Building page
	assert not at.exception and title(at) == "Building"
	assert len(values(at)) == 8 and "1,000 m²" in values(at)[0] and any("15.17 yr" in value for value in values(at))
	at.selectbox(key="buildingPicker").select("240117").run()
	assert any("10.93 yr" in value for value in values(at)) and len(at.get("image")) == 1

	goto(at, "proposal")
	assert title(at) == "Proposal" and "Dear owner," in text(at)
	goto(at, "analyze")
	assert at.expander[-1].label == "Agent steps · 2"


def test_what_if_recalculates_the_shown_buildings(monkeypatch, tmp_path):
	at = start(monkeypatch, FakeAgent(roof_png(tmp_path)))
	button(at, "Run analysis").click().run()
	goto(at, "assumptions")
	at.slider[1].set_value(0)  # incentive 0%
	button(at, "Recalculate").click().run()
	assert not at.exception and "What-if values are active" in text(at)

	goto(at, "building")
	payback = next(value for value in values(at) if "15.61 yr" in value)  # 2,218,672 / 142,145 with no ITC
	assert "+4.68 yr vs sourced defaults" in payback
	assert any("What-if assumptions are active" in info.value for info in at.info)

	goto(at, "assumptions")
	button(at, "Reset to sourced defaults").click().run()
	goto(at, "building")
	assert any("10.93 yr" in value for value in values(at)) and not at.info


def test_failure_falls_back_to_the_last_saved_run(monkeypatch, tmp_path):
	at = start(monkeypatch, FakeAgent(roof_png(tmp_path)))
	button(at, "Run analysis").click().run()  # saves the run to ROOFWATT_LAST_RUN

	st.cache_resource.clear()
	at = start(monkeypatch, FakeAgent(error=RuntimeError("429 RESOURCE_EXHAUSTED")))  # fresh session, no results yet
	button(at, "Run analysis").click().run()
	assert not at.exception and title(at) == "Analyze"
	assert "free quota is used up" in at.error[0].value and "last saved analysis" in at.error[0].value
	goto(at, "results")
	assert at.metric[0].value == "185" and any("Saved analysis" in info.value for info in at.info)


class QuotaSwitchAgent:
	"""Answers the first turn on Gemini, then hits the quota and answers on the local model, like QuotaFallbackAgent."""

	def __init__(self):
		self.useLocalModel = False
		self.turns = 0

	def invoke(self, state, config=None):
		self.turns += 1
		if self.turns > 1:
			self.useLocalModel = True
		return {"messages": [AIMessage(f"Reply {self.turns}.")]}


def sidebarModel(at):
	return [m.value for m in at.sidebar.markdown if m.value.startswith("Model:")]


def test_model_in_use_is_shown_and_a_quota_fallback_flips_the_switch_to_local(monkeypatch):
	at = start(monkeypatch, QuotaSwitchAgent())
	assert at.segmented_control(key="aiMode").value == "cloud"
	assert sidebarModel(at) == ["Model: Gemini · gemini-4-hydrogen"]
	assert "Gemini: :green[ACTIVE]" in [m.value for m in at.sidebar.markdown]

	button(at, "Run analysis").click().run()
	assert not at.exception and title(at) == "Results" and "did not rank buildings" in text(at) and "Reply 1." in text(at)
	goto(at, "analyze")
	assert "Model: Gemini · gemini-4-hydrogen" in [c.value for c in at.main.caption]

	button(at, "Run analysis").click().run()  # the quota runs out: the answer comes from Ollama, the switch moves
	assert at.segmented_control(key="aiMode").value == "local"
	assert any("Gemini free quota is used up" in c.value for c in at.sidebar.caption)
	goto(at, "analyze")
	assert "Model: Ollama · qwen3.5:4b (local fallback, Gemini quota exhausted)" in [c.value for c in at.main.caption]
	assert sidebarModel(at) == ["Model: Ollama · qwen3.5:4b (local)"]


def test_choosing_cloud_again_retries_gemini(monkeypatch):
	fake = QuotaSwitchAgent()
	at = start(monkeypatch, fake)
	button(at, "Run analysis").click().run()
	goto(at, "analyze")
	button(at, "Run analysis").click().run()
	assert fake.useLocalModel and at.segmented_control(key="aiMode").value == "local"
	at.segmented_control(key="aiMode").set_value("cloud").run()
	assert not fake.useLocalModel and sidebarModel(at) == ["Model: Gemini · gemini-4-hydrogen"]
	assert not any("quota is used up" in c.value for c in at.sidebar.caption)


def test_local_mode_lists_ollama_models_and_builds_a_local_agent(monkeypatch, tmp_path):
	calls = []
	at = start(monkeypatch, FakeAgent(roof_png(tmp_path)), calls)
	assert calls == [("cloud", "qwen3.5:4b")]
	at.segmented_control(key="aiMode").set_value("local").run()
	picker = at.selectbox(key="localModel")
	assert picker.options == ["llama3.2:3b", "qwen3.5:4b"] and picker.value == "qwen3.5:4b"  # the suggested default
	assert "Ollama: :green[ACTIVE]" in [m.value for m in at.sidebar.markdown]
	picker.select("llama3.2:3b").run()
	assert sidebarModel(at) == ["Model: Ollama · llama3.2:3b (local)"]
	button(at, "Run analysis").click().run()
	assert not at.exception and title(at) == "Results" and ("local", "llama3.2:3b") in calls


def test_local_mode_without_ollama_disables_run(monkeypatch):
	monkeypatch.setattr(agent.agent, "listLocalModels", lambda: ([], "Ollama is not running at http://localhost:11434."))
	at = start(monkeypatch, FakeAgent())
	at.segmented_control(key="aiMode").set_value("local").run()
	assert not at.exception and button(at, "Run analysis").disabled
	assert "Ollama: :red[OFFLINE]" in [m.value for m in at.sidebar.markdown]
	assert any("Ollama is not running" in c.value for c in at.main.caption)


def test_cloud_mode_without_a_gemini_key_disables_run(monkeypatch):
	monkeypatch.setattr(agent.agent, "hasGeminiKey", lambda: False)
	at = start(monkeypatch, FakeAgent())
	assert not at.exception and button(at, "Run analysis").disabled
	assert "Gemini: :red[OFFLINE]" in [m.value for m in at.sidebar.markdown]
	assert sidebarModel(at) == ["Model: unavailable · GOOGLE_API_KEY is not set, so the cloud model cannot run."]
