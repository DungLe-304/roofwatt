"""Collapsible list of the agent's tool calls (plan first, then each tool with a short result)."""


def traceMarkdown(trace: list[dict]) -> str:
	lines = []
	for number, step in enumerate(trace, start=1):
		result = step["result"] if step["ok"] else f"**{step['result']}**"
		call = f"{step['name']}({step['args']})"
		fence = "``" if "`" in call else "`"  # a double-backtick span may contain single backticks
		lines.append(f"{number}. {fence}{call}{fence} → {result}")
		lines.extend(f"    - {todo}" for todo in step.get("todos", []))
	return "\n".join(lines)


def showTrace(trace: list[dict]) -> None:
	import streamlit as st

	calls = len(trace)
	with st.expander(f"Agent steps · {calls} tool call{'s' if calls != 1 else ''}"):
		st.markdown(traceMarkdown(trace))
