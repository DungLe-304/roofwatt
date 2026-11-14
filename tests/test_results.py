"""Reading roof images out of an agent run's message history."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.results import roofImages


def tool_message(name, content, call_id="c1"):
	return ToolMessage(content=content, name=name, tool_call_id=call_id)


def test_collects_existing_images_in_order(tmp_path):
	first, second = tmp_path / "a.jpeg", tmp_path / "b.jpeg"
	first.write_bytes(b"x"), second.write_bytes(b"y")
	messages = [
		HumanMessage("pitch the top building"),
		tool_message("rankBuildings", '{"ranked": []}'),
		tool_message("getRoofImage", f'{{"buildingId": "1", "imagePath": "{first}"}}', "c2"),
		tool_message("getRoofImage", f'{{"buildingId": "2", "imagePath": "{second}"}}', "c3"),
		AIMessage("done"),
	]
	assert roofImages(messages) == [("1", str(first)), ("2", str(second))]


def test_skips_errors_missing_files_duplicates_and_bad_json(tmp_path):
	image = tmp_path / "a.jpeg"
	image.write_bytes(b"x")
	messages = [
		tool_message("getRoofImage", '{"buildingId": "1", "error": "Vexcel rejected VEXCEL_API_KEY (HTTP 401)"}'),
		tool_message("getRoofImage", f'{{"buildingId": "2", "imagePath": "{tmp_path / "gone.jpeg"}"}}'),
		tool_message("getRoofImage", "not json"),
		tool_message("getRoofImage", f'{{"buildingId": "3", "imagePath": "{image}"}}'),
		tool_message("getRoofImage", f'{{"buildingId": "3", "imagePath": "{image}"}}'),
	]
	assert roofImages(messages) == [("3", str(image))]
