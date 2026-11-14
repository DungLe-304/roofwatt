"""Streamlit app with a fake agent: reply text, roof image, ranked map and table are rendered (no LLM call)."""

import json

from langchain_core.messages import AIMessage, ToolMessage
from streamlit.testing.v1 import AppTest

import agent.agent


RANKING = {"city": "Houston", "propertyType": "Office", "totalMatches": 185, "rankedCount": 173,
	"excluded": {"errors": [], "belowMinimumSize": 12, "noPayback": 0},
	"assumptions": {"usableFactor": 0.6, "minSystemKw": 50},
	"ranked": [{"rank": 1, "address": "5959 Corporate Dr", "buildingId": "240117", "usableRoofM2": 7906.04,
		"systemKw": 1167.72, "annualKwh": 1660572.5, "annualSavingsUsd": 142145.01, "costPerWattUsd": 1.9,
		"capexUsd": 2218672.19, "netCapexUsd": 1553070.53, "simplePaybackYr": 10.93, "co2TonsPerYear": 552.76}]}


def shown(at):
	"""(roof images, ranked tables, maps, tool traces, detail metrics) currently on the page."""
	return (len(at.get("image")), len(at.dataframe), len(at.get("deck_gl_json_chart")), len(at.expander), len(at.metric))


class FakeAgent:
	def __init__(self, image_path):
		self.image_path = image_path
		self.received = None

	def invoke(self, state):
		first_turn = self.received is None
		self.received = state["messages"]
		if not first_turn:
			return {"messages": [AIMessage("You're welcome.")]}
		return {"messages": [
			AIMessage("", tool_calls=[{"name": "rankBuildings", "args": {"city": "Houston"}, "id": "c0"},
				{"name": "getRoofImage", "args": {"buildingId": "240117"}, "id": "c1"}]),
			ToolMessage(content=json.dumps(RANKING), name="rankBuildings", tool_call_id="c0"),
			ToolMessage(content=f'{{"buildingId": "240117", "imagePath": "{self.image_path}"}}', name="getRoofImage", tool_call_id="c1"),
			AIMessage("Top building: 240117."),
		]}


def test_reply_and_roof_image_are_shown_and_kept_in_history(tmp_path, monkeypatch):
	image = tmp_path / "roof.png"
	image.write_bytes(bytes.fromhex(
		"89504e470d0a1a0a0000000d4948445200000001000000010806000000"
		"1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"))
	fake = FakeAgent(image)
	monkeypatch.setattr(agent.agent, "createRoofWattAgent", lambda: fake)

	at = AppTest.from_file("../app.py", default_timeout=30).run()
	at.chat_input[0].set_value("pitch the top building").run()
	assert not at.exception and not at.error
	assert any("Top building: 240117." in m.value for m in at.markdown)
	assert shown(at) == (1, 1, 1, 1, 8)  # the roof image appears once, in the detail panel
	assert at.dataframe[0].value["Address"].tolist() == ["5959 Corporate Dr"]
	assert at.expander[0].label == "Agent steps · 2 tool calls"
	assert {m.label: m.value for m in at.metric}["Payback"] == "10.93 yr"  # rank 1 is detailed by default
	assert fake.received == [{"role": "user", "content": "pitch the top building"}]

	at.chat_input[0].set_value("thanks").run()  # rerun: the earlier image, map and table stay in the history
	assert not at.exception and not at.error
	assert shown(at) == (1, 1, 1, 1, 8)
	assert fake.received[-2:] == [{"role": "assistant", "content": "Top building: 240117."}, {"role": "user", "content": "thanks"}]
