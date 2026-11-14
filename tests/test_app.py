"""Streamlit app with a fake agent: the reply text and the roof image are both rendered (no LLM call)."""

from langchain_core.messages import AIMessage, ToolMessage
from streamlit.testing.v1 import AppTest

import agent.agent


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
	assert len(at.get("image")) == 1
	assert fake.received == [{"role": "user", "content": "pitch the top building"}]

	at.chat_input[0].set_value("thanks").run()  # rerun: the earlier image stays in the history
	assert len(at.get("image")) == 1
	assert fake.received[-2:] == [{"role": "assistant", "content": "Top building: 240117."}, {"role": "user", "content": "thanks"}]
