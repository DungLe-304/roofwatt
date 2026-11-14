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
