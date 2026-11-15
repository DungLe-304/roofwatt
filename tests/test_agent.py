"""Guards against tools disappearing while the system prompt still tells the model to call them."""

import re

from agent import agent
from agent.tools import roofWattTools


def test_every_tool_named_in_the_prompt_is_registered():
	registered = {tool.__name__ for tool in roofWattTools}
	candidates = set(re.findall(r"\b([a-z]+[A-Z][A-Za-z]+)\b", agent.systemPrompt))
	named = {name for name in candidates if name[0].islower() and name not in {"buildingId", "buildingSqft",
	         "simplePaybackYr", "co2TonsPerYear", "belowMinimumSize"}}
	assert named, "expected the prompt to name some tools"
	assert named <= registered, f"prompt names unregistered tools: {sorted(named - registered)}"


class Reply:
	def __init__(self, payload=None, error=None):
		self.payload, self.error = payload, error

	def raise_for_status(self):
		if self.error:
			raise self.error

	def json(self):
		return self.payload


def test_list_local_models_reads_ollama_tags(monkeypatch):
	seen = []
	def fake_get(url, timeout):
		seen.append(url)
		return Reply({"models": [{"name": "qwen3.5:4b"}, {"name": "llama3.2:3b"}]})
	monkeypatch.setattr(agent.requests, "get", fake_get)
	assert agent.listLocalModels("http://box:11434/") == (["llama3.2:3b", "qwen3.5:4b"], None)
	assert seen == ["http://box:11434/api/tags"]


def test_list_local_models_reports_ollama_down(monkeypatch):
	def refuse(url, timeout):
		raise agent.requests.ConnectionError("Connection refused")
	monkeypatch.setattr(agent.requests, "get", refuse)
	assert agent.listLocalModels("http://localhost:11434") == ([], "Ollama is not running at `http://localhost:11434`.")


def test_create_agent_local_mode_uses_only_ollama_and_cloud_keeps_a_fallback(monkeypatch):
	monkeypatch.setattr(agent, "createLocalAgent", lambda name=None: ("local", name))
	monkeypatch.setattr(agent, "createCloudAgent", lambda: "gemini")
	assert agent.createAgent(agent.LOCAL, "llama3.2:3b") == ("local", "llama3.2:3b")
	cloud = agent.createAgent(agent.CLOUD, "llama3.2:3b")
	assert isinstance(cloud, agent.QuotaFallbackAgent) and cloud.primaryAgent == "gemini"
	assert cloud.localAgent == ("local", "llama3.2:3b") and not cloud.useLocalModel


class Answers:
	def __init__(self, reply=None, error=None):
		self.reply, self.error, self.calls = reply, error, 0

	def invoke(self, state, config=None):
		self.calls += 1
		if self.error:
			raise self.error
		return self.reply


def test_quota_error_switches_to_the_local_agent_for_good():
	gemini, local = Answers(error=RuntimeError("429 RESOURCE_EXHAUSTED")), Answers(reply="local answer")
	fallback = agent.QuotaFallbackAgent(gemini, local)
	assert fallback.invoke({}) == "local answer" and fallback.useLocalModel
	assert fallback.invoke({}) == "local answer" and gemini.calls == 1


def test_other_errors_are_not_hidden_by_the_fallback():
	fallback = agent.QuotaFallbackAgent(Answers(error=ValueError("bad request")), Answers(reply="unused"))
	try:
		fallback.invoke({})
	except ValueError:
		assert not fallback.useLocalModel
	else:
		raise AssertionError("expected the Gemini error to propagate")
