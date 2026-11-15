"""Read tool results (roof images, building ranking) back out of an agent run's message history (for the UI)."""

import json
import re
from pathlib import Path


def roofImages(messages) -> list[tuple[str, str]]:
	"""(buildingId, imagePath) for every successful getRoofImage call whose file exists, in call order, deduplicated."""
	images = []
	for message in messages:
		if getattr(message, "type", None) != "tool" or getattr(message, "name", None) != "getRoofImage":
			continue
		try:
			result = json.loads(message.content)
		except (TypeError, ValueError):
			continue
		path = result.get("imagePath") if isinstance(result, dict) else None
		image = (str(result.get("buildingId")), path)
		if path and Path(path).is_file() and image not in images:
			images.append(image)
	return images


def rankingResult(messages) -> dict | None:
	"""The result of the last successful rankBuildings call that ranked at least one building, else None."""
	for message in reversed(messages):
		if getattr(message, "type", None) != "tool" or getattr(message, "name", None) != "rankBuildings":
			continue
		try:
			result = json.loads(message.content)
		except (TypeError, ValueError):
			continue
		if isinstance(result, dict) and result.get("ranked"):
			return result
	return None


def _shortResult(name: str, content) -> tuple[bool, str]:
	try:
		result = json.loads(content)
	except (TypeError, ValueError):
		return True, "ok"
	if not isinstance(result, dict):
		return True, "ok"
	if result.get("error"):
		error = str(result["error"])
		return False, f"error: {error[:120]}{'…' if len(error) > 120 else ''}"
	if name == "rankBuildings" and "ranked" in result:
		return True, f"ranked {len(result['ranked'])} of {result.get('rankedCount')} ({result.get('totalMatches')} matches)"
	if name == "getRoofImage" and result.get("imagePath"):
		return True, "image ready"
	if result.get("simplePaybackYr") is not None:
		return True, f"payback {result['simplePaybackYr']:.2f} yr"
	return True, "ok"


def _number(text: str, field: str) -> int | None:
	"""A count from tool output that is JSON ("field": 3) or a pydantic repr (field=3)."""
	match = re.search(rf'["\']?{field}["\']?\s*[:=]\s*(\d+)', text)
	return int(match.group(1)) if match else None


def toolSummary(name: str, content, args: dict | None = None) -> tuple[bool, str]:
	"""(ok, one human-readable line) for a tool result, for the live and the saved agent trace."""
	text = str(getattr(content, "content", content) or "")
	try:
		result = json.loads(text)
	except (TypeError, ValueError):
		result = None
	if isinstance(result, dict) and result.get("error"):
		return _shortResult(name, text)
	if name == "rankBuildings" and isinstance(result, dict) and "ranked" in result:
		kind = str(result.get("propertyType", "")).lower()
		notes = [f"{result.get('totalMatches')} {kind} buildings in {result.get('city')} screened".replace("  ", " "),
			f"{result.get('rankedCount')} ranked"]
		tooSmall = (result.get("excluded") or {}).get("belowMinimumSize")
		if tooSmall:
			notes.append(f"{tooSmall} too small")
		return True, " · ".join(notes) + f" → top {len(result['ranked'])} kept"
	if name == "searchBuildings":
		found, total = len(re.findall(r"buildingId", text)), _number(text, "totalMatches")
		return True, f"{found} buildings found" + (f" (of {total} matches)" if total is not None else "")
	if name == "getBuilding":
		match = re.search(r'["\']?address["\']?\s*[:=]\s*["\']([^"\']+)', text)
		return True, f"details loaded: {match.group(1)}" if match else "details loaded"
	if name == "write_todos":
		todos = (args or {}).get("todos") or []
		return True, f"planned {len(todos)} step{'s' if len(todos) != 1 else ''}"
	if name == "computeFinancials" and isinstance(result, dict) and result.get("simplePaybackYr") is not None:
		return True, f"payback {result['simplePaybackYr']:.2f} yr · ${result.get('annualSavingsUsd', 0):,.0f}/yr savings"
	if name == "getRoofImage" and isinstance(result, dict) and result.get("imagePath"):
		return True, "aerial roof image ready"
	return _shortResult(name, text)


MAX_ARGS_CHARS = 160  # deepagents' write_file/task args can hold whole documents


def toolTrace(messages) -> list[dict]:
	"""Every tool call the agent made, in order: name, args (as text), ok, short result; write_todos adds its items."""
	results = {getattr(m, "tool_call_id", None): m for m in messages if getattr(m, "type", None) == "tool"}
	steps = []
	for message in messages:
		for toolCall in getattr(message, "tool_calls", None) or []:
			name, args = toolCall["name"], toolCall.get("args") or {}
			argsText = ", ".join(f"{key}={json.dumps(value)}" for key, value in args.items() if key != "todos")
			step = {"name": name, "args": argsText if len(argsText) <= MAX_ARGS_CHARS else argsText[:MAX_ARGS_CHARS] + "…"}
			if name == "write_todos":
				step["todos"] = [str(todo.get("content", "")) for todo in args.get("todos", []) if isinstance(todo, dict)]
			reply = results.get(toolCall.get("id"))
			step["ok"], step["result"] = _shortResult(name, reply.content) if reply is not None else (True, "no result")
			step["summary"] = toolSummary(name, reply.content, args)[1] if reply is not None else "no result"
			steps.append(step)
	return steps
