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
