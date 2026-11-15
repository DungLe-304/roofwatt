"""Reading roof images and the ranking out of an agent run's message history."""

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.results import rankingResult, roofImages, toolTrace


def tool_message(name, content, call_id="c1"):
	return ToolMessage(content=content, name=name, tool_call_id=call_id)


def test_collects_existing_images_in_order(tmp_path):
	first, second = tmp_path / "a.jpeg", tmp_path / "b.jpeg"
	first.write_bytes(b"x"), second.write_bytes(b"y")
	messages = [
		HumanMessage("pitch the top building"),
		tool_message("rankBuildings", '{"ranked": []}'),
		tool_message("getRoofImage", json.dumps({"buildingId": "1", "imagePath": str(first)}), "c2"),
		tool_message("getRoofImage", json.dumps({"buildingId": "2", "imagePath": str(second)}), "c3"),
		AIMessage("done"),
	]
	assert roofImages(messages) == [("1", str(first)), ("2", str(second))]


def test_skips_errors_missing_files_duplicates_and_bad_json(tmp_path):
	image = tmp_path / "a.jpeg"
	image.write_bytes(b"x")
	messages = [
		tool_message("getRoofImage", '{"buildingId": "1", "error": "Vexcel rejected VEXCEL_API_KEY (HTTP 401)"}'),
		tool_message("getRoofImage", json.dumps({"buildingId": "2", "imagePath": str(tmp_path / "gone.jpeg")})),
		tool_message("getRoofImage", "not json"),
		tool_message("getRoofImage", json.dumps({"buildingId": "3", "imagePath": str(image)})),
		tool_message("getRoofImage", json.dumps({"buildingId": "3", "imagePath": str(image)})),
	]
	assert roofImages(messages) == [("3", str(image))]


def ranking(ranked, **extra):
	return json.dumps({"city": "Houston", "propertyType": "Office", "totalMatches": 3, "rankedCount": len(ranked),
		"excluded": {"errors": [], "belowMinimumSize": 0, "noPayback": 0}, "ranked": ranked, "assumptions": {}} | extra)


def test_ranking_result_is_the_last_successful_rank_call():
	first, last = [{"rank": 1, "buildingId": "1"}], [{"rank": 1, "buildingId": "2"}]
	messages = [
		tool_message("rankBuildings", ranking(first)),
		tool_message("rankBuildings", ranking(last), "c2"),
		tool_message("rankBuildings", '{"error": "no buildings match"}', "c3"),
		tool_message("rankBuildings", "not json", "c4"),
		AIMessage("done"),
	]
	assert rankingResult(messages)["ranked"] == last


def test_ranking_result_is_none_without_a_ranked_list():
	messages = [
		HumanMessage("hi"),
		tool_message("computeFinancials", ranking([{"rank": 1, "buildingId": "1"}])),
		tool_message("rankBuildings", ranking([]), "c2"),
		AIMessage("hello"),
	]
	assert rankingResult(messages) is None


def call(name, args, call_id):
	return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def test_tool_trace_pairs_calls_with_short_results_in_order():
	todos = [{"content": "Rank Houston offices", "status": "in_progress"}, {"content": "Draft pitch", "status": "pending"}]
	messages = [
		HumanMessage("find offices"),
		AIMessage("", tool_calls=[call("write_todos", {"todos": todos}, "t1")]),
		tool_message("write_todos", "Updated todo list", "t1"),
		AIMessage("", tool_calls=[call("rankBuildings", {"city": "Houston", "limit": 10}, "t2"),
			call("computeFinancials", {"buildingId": "9"}, "t3")]),
		tool_message("rankBuildings", ranking([{"rank": 1, "buildingId": "1"}], rankedCount=173, totalMatches=185), "t2"),
		tool_message("computeFinancials", '{"buildingId": "9", "error": "' + "x" * 300 + '"}', "t3"),
		AIMessage("", tool_calls=[call("getRoofImage", {"buildingId": "1"}, "t4")]),
		AIMessage("done"),
	]
	trace = toolTrace(messages)
	assert [step["name"] for step in trace] == ["write_todos", "rankBuildings", "computeFinancials", "getRoofImage"]
	assert trace[0]["todos"] == ["Rank Houston offices", "Draft pitch"]
	assert trace[1]["args"] == 'city="Houston", limit=10'
	assert trace[1]["result"] == "ranked 1 of 173 (185 matches)"
	assert trace[2]["ok"] is False and trace[2]["result"].startswith("error: xxx") and len(trace[2]["result"]) <= 130
	assert trace[3]["result"] == "no result"


def test_tool_trace_is_empty_without_tool_calls():
	assert toolTrace([HumanMessage("hi"), AIMessage("hello")]) == []


def test_tool_trace_truncates_long_args():
	messages = [AIMessage("", tool_calls=[call("write_file", {"file_path": "/pitch.md", "content": "x" * 5000}, "w1")])]
	args = toolTrace(messages)[0]["args"]
	assert args.startswith('file_path="/pitch.md", content="xxx') and args.endswith("…") and len(args) <= 161
