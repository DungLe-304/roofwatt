"""Streamlit app with fake agents (no LLM call): empty state, live run, cards, detail, proposal, what-if, fallback."""

import json

import pytest
import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage
from streamlit.testing.v1 import AppTest

import agent.agent

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
	"""Fresh cached agent per test; the last-run fallback file goes to tmp_path, not the demo cache."""
	st.cache_resource.clear()
	monkeypatch.setenv("ROOFWATT_LAST_RUN", str(tmp_path / "last_run.json"))


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


def start(monkeypatch, fake):
	monkeypatch.setattr(agent.agent, "createRoofWattAgent", lambda **kwargs: fake)
	return AppTest.from_file("../app.py", default_timeout=30).run()


def button(at, label):
	return next(b for b in at.button if b.label == label)


def metrics(at):
	return {m.label: m.value for m in at.metric}


def test_empty_state_explains_the_three_steps_and_prefills_the_demo_query(monkeypatch):
	at = start(monkeypatch, FakeAgent())
	assert not at.exception
	assert at.text_area(key="query").value.startswith("Find the 10 office buildings in Houston")
	assert [m.value for m in at.markdown if m.value.startswith("#### ")] == [
		"#### :material/travel_explore: 1 · Scan", "#### :material/solar_power: 2 · Analyze", "#### :material/edit_note: 3 · Pitch"]
	assert not at.metric


def test_run_shows_kpis_map_cards_detail_proposal_and_trace(monkeypatch, tmp_path):
	fake = FakeAgent(roof_png(tmp_path))
	at = start(monkeypatch, fake)
	button(at, "Run analysis").click().run()
	assert not at.exception and not at.error
	assert fake.received[0][-1]["content"].startswith("Find the 10 office buildings")

	shown = metrics(at)
	assert shown["Buildings analyzed"] == "185"
	assert shown["Solar capacity · top 2"] == "1,315 kW"
	assert shown["Annual savings · top 2"] == "$159,864/yr"
	assert shown["CO₂ avoided · top 2"] == "622 t/yr"
	assert shown["Payback"] == "10.93 yr"  # rank 1 is detailed by default
	assert len(at.get("deck_gl_json_chart")) == 1 and len(at.get("image")) == 1
	assert at.expander[0].label == "How the agent got here · 2 steps"
	assert any("Dear owner," in m.value for m in at.markdown)  # the proposal letter
	assert any(m.value.startswith("Top 2 offices") for m in at.markdown)  # rest of the answer, in an expander
	assert [b.label for b in at.button if b.key and b.key.startswith("pick-")] == ["Viewing", "Details"]

	at.button(key="pick-999999999").click().run()  # select the second card
	assert not at.exception
	assert metrics(at)["Payback"] == "15.17 yr"
	assert any("#2 · Second Building" in m.value for m in at.markdown)


def test_what_if_recalculates_the_shown_buildings(monkeypatch, tmp_path):
	at = start(monkeypatch, FakeAgent(roof_png(tmp_path)))
	button(at, "Run analysis").click().run()
	at.sidebar.slider[1].set_value(0)  # incentive 0%
	button(at, "Recalculate").click().run()
	assert not at.exception
	assert any("What-if assumptions" in w.value for w in at.warning)
	assert metrics(at)["Payback"] == "15.61 yr"  # 2,218,672 / 142,145 with no ITC
	button(at, "Reset to sourced defaults").click().run()
	assert metrics(at)["Payback"] == "10.93 yr" and not at.warning


def test_failure_falls_back_to_the_last_saved_run(monkeypatch, tmp_path):
	at = start(monkeypatch, FakeAgent(roof_png(tmp_path)))
	button(at, "Run analysis").click().run()  # saves the run to ROOFWATT_LAST_RUN

	st.cache_resource.clear()
	at = start(monkeypatch, FakeAgent(error=RuntimeError("429 RESOURCE_EXHAUSTED")))  # fresh session, no results yet
	button(at, "Run analysis").click().run()
	assert not at.exception
	assert "free quota is used up" in at.error[0].value and "last saved analysis" in at.error[0].value
	assert metrics(at)["Payback"] == "10.93 yr"
	assert any("offline fallback" in i.value for i in at.info)


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


def test_model_used_is_shown_with_the_answer_and_in_the_sidebar(monkeypatch):
	at = start(monkeypatch, QuotaSwitchAgent())
	sidebar = lambda: [c.value for c in at.sidebar.caption if c.value.startswith("Model:")]
	assert sidebar() == ["Model: Gemini · gemini-4-hydrogen"]

	button(at, "Run analysis").click().run()
	assert not at.exception and not at.error
	assert "Model: Gemini · gemini-4-hydrogen" in [c.value for c in at.main.caption]

	button(at, "Run analysis").click().run()
	ollama = "Model: Ollama · qwen3.5:4b (local fallback, Gemini quota exhausted)"
	assert ollama in [c.value for c in at.main.caption]
	assert sidebar() == [ollama]
