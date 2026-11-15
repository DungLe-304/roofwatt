"""The drafted owner proposal is split from the ranking summary in the agent's final answer."""

from ui.proposal import splitProposal


def test_splits_at_a_pitch_heading():
	text = "Here are the top 10.\n\n| # | Address |\n|---|---|\n\n## Pitch for 5959 Corporate Dr\nDear owner,\nSolar pays."
	summary, proposal = splitProposal(text)
	assert summary.startswith("Here are the top 10.") and summary.endswith("|---|---|")
	assert proposal == "## Pitch for 5959 Corporate Dr\nDear owner,\nSolar pays."


def test_splits_at_a_bold_heading_or_a_dear_line():
	assert splitProposal("Table.\n**Proposal letter**\nHello")[1] == "**Proposal letter**\nHello"
	assert splitProposal("Table.\nDear Property Owner,\nHello") == ("Table.", "Dear Property Owner,\nHello")


def test_no_proposal_keeps_the_whole_answer():
	assert splitProposal("Found 5 buildings. The pitch could not be drafted") == ("Found 5 buildings. The pitch could not be drafted", None)
	assert splitProposal("") == ("", None)


def test_a_repeated_greeting_is_dropped():
	# qwen3.5:4b wrote "Dear Property Owner," then restarted the letter with "**Dear Property Owner,**".
	text = ("| 1 | 240117 |\n\n## Proposal letter\n\nDear Property Owner,\n\nThe figures are estimates.\n\n"
		"**Dear Property Owner,**\n\nYour property at 5959 Corporate Dr...\n\nSincerely,\nThe RoofWatt team")
	_, proposal = splitProposal(text)
	assert proposal.count("Dear Property Owner") == 1
	assert proposal.startswith("## Proposal letter\n\nDear Property Owner,\n\nThe figures are estimates.")
	assert "Your property at 5959 Corporate Dr" in proposal and proposal.endswith("The RoofWatt team")


def test_a_letter_with_one_greeting_is_unchanged():
	text = "Summary.\n\nDear Ms. Lee,\n\nBody mentions dear friends.\n\nSincerely,\nRoofWatt"
	assert splitProposal(text) == ("Summary.", "Dear Ms. Lee,\n\nBody mentions dear friends.\n\nSincerely,\nRoofWatt")
