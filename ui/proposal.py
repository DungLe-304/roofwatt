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


def splitProposal(text: str) -> tuple[str, str | None]:
	"""(summary, proposal): the proposal starts at the first pitch/proposal/letter heading or a "Dear ..." line."""
	lines = (text or "").splitlines()
	for index, line in enumerate(lines):
		if _startsProposal(line):
			proposal = "\n".join(lines[index:]).strip()
			return "\n".join(lines[:index]).strip(), proposal or None
	return (text or "").strip(), None
