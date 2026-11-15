"""Vexcel roof image fetch + file cache. HTTP is faked; nothing touches the network."""

import pytest

from data import cache, imagery


class FakeResponse:
	def __init__(self, status=200, content=b"\xff\xd8jpeg-bytes", content_type="image/jpeg"):
		self.status_code = status
		self.content = content
		self.headers = {"content-type": content_type}
		self.text = content.decode("latin-1")


@pytest.fixture
def env(tmp_path, monkeypatch):
	monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
	monkeypatch.setenv("VEXCEL_API_KEY", "test-token")
	state = {"calls": [], "response": FakeResponse()}

	def fake_get(url, params, timeout):
		state["calls"].append((url, params))
		if isinstance(state["response"], Exception):
			raise state["response"]
		return state["response"]

	monkeypatch.setattr(imagery.requests, "get", fake_get)
	return state


def test_fetches_image_by_center_point_and_caches_it(env, tmp_path):
	path = imagery.get_roof_image("b1", 29.71, -95.55, extent_m=150, size_px=640)
	assert path.read_bytes() == b"\xff\xd8jpeg-bytes"
	assert path.suffix == ".jpeg" and path.is_relative_to(tmp_path)
	url, params = env["calls"][0]
	assert url == "https://api.vexcelgroup.com/v2/ortho/extract"
	assert params["wkt"] == "POINT(-95.55 29.71)"  # WKT is lon lat
	assert params["layer"] == "urban"
	assert params["bbox-dimensions"] == "150,150"
	assert params["destination-dimensions"] == "640,640,fit"
	assert params["image-format"] == "jpeg"
	assert params["api_key"] == "test-token"


def test_extent_is_part_of_the_cache_key(env):
	imagery.get_roof_image("b1", 29.71, -95.55, extent_m=150)
	imagery.get_roof_image("b1", 29.71, -95.55, extent_m=300)
	assert len(env["calls"]) == 2


def test_no_coverage_raises(env):
	env["response"] = FakeResponse(204, b"", "text/plain")
	with pytest.raises(RuntimeError, match="no imagery"):
		imagery.get_roof_image("b1", 29.71, -95.55)


def test_second_call_is_served_from_cache(env):
	first = imagery.get_roof_image("b1", 29.71, -95.55)
	second = imagery.get_roof_image("b1", 29.71, -95.55)
	assert first == second
	assert len(env["calls"]) == 1


def test_png_response_keeps_png_extension(env):
	env["response"] = FakeResponse(content=b"\x89PNG", content_type="image/png")
	assert imagery.get_roof_image("b2", 29.7, -95.5).suffix == ".png"


def test_rejected_token_raises_clear_error_and_caches_nothing(env, tmp_path):
	env["response"] = FakeResponse(401, b'{"status": 401,"message": "Unauthorized"}', "application/json")
	with pytest.raises(RuntimeError, match="401"):
		imagery.get_roof_image("b1", 29.71, -95.55)
	assert not any(tmp_path.rglob("*.*"))


def test_missing_token_raises_before_any_request(env, monkeypatch):
	monkeypatch.delenv("VEXCEL_API_KEY")
	with pytest.raises(RuntimeError, match="VEXCEL_API_KEY"):
		imagery.get_roof_image("b1", 29.71, -95.55)
	assert env["calls"] == []


def test_cache_keys_are_filesystem_safe(tmp_path, monkeypatch):
	monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
	path = cache.write_bytes("vexcel", "../evil/../id", ".jpeg", b"x")
	assert path.parent == tmp_path / "vexcel"
	assert cache.find("vexcel", "../evil/../id") == path


def test_connection_errors_never_contain_the_api_key(env):
	env["response"] = imagery.requests.ConnectionError("Max retries exceeded with url: /v2/ortho/extract?api_key=test-token")
	with pytest.raises(imagery.requests.ConnectionError) as error:
		imagery.get_roof_image("b1", 29.76, -95.37, extent_m=80)
	assert "test-token" not in str(error.value) and "api_key=***" in str(error.value)
