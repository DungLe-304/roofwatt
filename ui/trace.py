"""The agent's tool calls as a readable timeline: live while the agent runs, then saved under an expander."""

import queue

from langchain_core.callbacks import BaseCallbackHandler

from agent.results import toolSummary

STEP_STYLE = {  # tool name -> (Material icon, human label)
	"write_todos": (":material/checklist:", "Plan"),
	"rankBuildings": (":material/leaderboard:", "Rank buildings"),
	"searchBuildings": (":material/search:", "Search buildings"),
	"getBuilding": (":material/apartment:", "Building details"),
	"analyzeRoof": (":material/roofing:", "Roof area"),
	"estimateSolar": (":material/solar_power:", "Solar estimate"),
	"computeFinancials": (":material/payments:", "Financials"),
	"getRoofImage": (":material/satellite_alt:", "Aerial image"),
}


def stepLine(name: str, summary: str, ok: bool = True, running: bool = False) -> str:
	icon, label = STEP_STYLE.get(name, (":material/build:", name))
	if running:
		return f"{icon} **{label}** · _running…_"
	return f"{icon} **{label}** · {summary}" if ok else f":material/error: **{label}** · :red[{summary}]"


def traceMarkdown(trace: list[dict]) -> str:
	lines = []
	for number, step in enumerate(trace, start=1):
		summary = step.get("summary") or step["result"]
		lines.append(f"{number}. {stepLine(step['name'], summary, step['ok'])}")
		lines.extend(f"    - {todo}" for todo in step.get("todos", []))
	return "\n".join(lines)


def showTrace(trace: list[dict], model: str | None = None) -> None:
	import streamlit as st

	calls = len(trace)
	with st.expander(f"How the agent got here · {calls} step{'s' if calls != 1 else ''}", icon=":material/route:"):
		st.markdown(traceMarkdown(trace) or "The agent answered without calling a tool.")
		if model:
			st.caption(model)


class LiveTrace(BaseCallbackHandler):
	"""LangChain callback that queues tool start/end events; the Streamlit thread drains and draws them.

	Tool calls may run on worker threads, so the handler never touches Streamlit itself.
	"""

	def __init__(self):
		self.events = queue.Queue()
		self.steps = {}  # run_id -> {"name", "args", "done", "ok", "summary"}, in start order

	def on_chat_model_start(self, serialized, messages, **kwargs):
		self.events.put(("thinking", None, None))

	def on_tool_start(self, serialized, input_str, *, run_id, inputs=None, **kwargs):
		name = kwargs.get("name") or (serialized or {}).get("name") or "tool"
		self.events.put(("start", run_id, {"name": name, "args": inputs if isinstance(inputs, dict) else {}}))

	def on_tool_end(self, output, *, run_id, **kwargs):
		self.events.put(("end", run_id, output))

	def on_tool_error(self, error, *, run_id, **kwargs):
		self.events.put(("error", run_id, error))

	def drain(self) -> str | None:
		"""Apply queued events; returns a status label for the latest event, or None if nothing new."""
		label = None
		while True:
			try:
				kind, runId, payload = self.events.get_nowait()
			except queue.Empty:
				return label
			if kind == "thinking":
				label = "Thinking…"
			elif kind == "start":
				self.steps[runId] = payload | {"done": False, "ok": True, "summary": ""}
				label = f"{STEP_STYLE.get(payload['name'], ('', payload['name']))[1]}…"
			elif runId in self.steps:
				step = self.steps[runId]
				if kind == "end":
					step["ok"], step["summary"] = toolSummary(step["name"], payload, step["args"])
				else:
					step["ok"], step["summary"] = False, f"error: {str(payload)[:120]}"
				step["done"] = True

	def markdown(self) -> str:
		return "\n".join(f"{number}. {stepLine(step['name'], step['summary'], step['ok'], running=not step['done'])}"
			for number, step in enumerate(self.steps.values(), start=1))
