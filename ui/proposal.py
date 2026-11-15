"""Split the agent's final answer into the ranking summary and the drafted owner proposal (display only)."""

import re

_KEYWORD = re.compile(r"\b(pitch|proposal|letter)\b", re.IGNORECASE)
_HEADING = re.compile(r"^\s*(#{1,6}\s+|\*\*|__)")


def _startsProposal(line: str) -> bool:
	text = line.strip()
	if text.lower().startswith(("dear ", "subject:", "**subject")):
		return True
	isHeading = bool(_HEADING.match(text)) or (text.endswith(":") and len(text) < 80)
	return isHeading and bool(_KEYWORD.search(text))


def _greeting(line: str) -> str | None:
	"""A "Dear ..." line without markdown emphasis, lowercased; None for any other line."""
	text = line.strip().strip("*_ ").lower()
	return text if text.startswith("dear ") else None


def _dropRepeatedGreeting(lines: list[str]) -> list[str]:
	"""Small local models sometimes restart the letter with the same "Dear ..." line; keep only the first."""
	first, kept = None, []
	for line in lines:
		greeting = _greeting(line)
		if greeting and first is not None and greeting == first:
			if kept and not kept[-1].strip():
				kept.pop()  # and the blank line before it
			continue
		first = first or greeting
		kept.append(line)
	return kept


def splitProposal(text: str) -> tuple[str, str | None]:
	"""(summary, proposal): the proposal starts at the first pitch/proposal/letter heading or a "Dear ..." line."""
	lines = (text or "").splitlines()
	for index, line in enumerate(lines):
		if _startsProposal(line):
			proposal = "\n".join(_dropRepeatedGreeting(lines[index:])).strip()
			return "\n".join(lines[:index]).strip(), proposal or None
	return (text or "").strip(), None
