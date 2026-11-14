"""PVWatts client tests. HTTP is faked; no network calls."""

import pytest

from models import solar


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise solar.requests.HTTPError(f"HTTP {self.status_code}")


def ok(ac_annual):
    return FakeResponse(200, {"errors": [], "outputs": {"ac_annual": ac_annual}})


@pytest.fixture
def calls(monkeypatch, tmp_path):
    """Queue of fake responses; records request params. Cache goes to tmp_path."""
    monkeypatch.setattr(solar, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(solar.time, "sleep", lambda s: None)
    monkeypatch.setenv("NLR_API_KEY", "test-key")
    state = {"responses": [], "params": []}

    def fake_get(url, params, timeout):
        state["params"].append(params)
        return state["responses"].pop(0)

    monkeypatch.setattr(solar.requests, "get", fake_get)
    return state


def test_returns_annual_kwh_and_sends_roof_mount_params(calls):
    calls["responses"] = [ok(137_947.7)]
    r = solar.estimate_solar("b1", 29.76, -95.37, 100, tilt_deg=10)
    assert (r.building_id, r.system_kw, r.annual_kwh) == ("b1", 100, 137_947.7)
    p = calls["params"][0]
    assert p["array_type"] == 1 and p["azimuth"] == 180 and p["tilt"] == 10
    assert p["system_capacity"] == 100 and p["losses"] == 14
    assert (p["lat"], p["lon"], p["api_key"]) == (29.76, -95.37, "test-key")


def test_second_identical_call_is_served_from_cache(calls):
    calls["responses"] = [ok(1000.0)]
    solar.estimate_solar("b1", 29.76, -95.37, 100, tilt_deg=10)
    r = solar.estimate_solar("b1", 29.76, -95.37, 100, tilt_deg=10)
    assert r.annual_kwh == 1000.0
    assert len(calls["params"]) == 1


def test_different_system_size_is_not_a_cache_hit(calls):
    calls["responses"] = [ok(1000.0), ok(2000.0)]
    solar.estimate_solar("b1", 29.76, -95.37, 100, tilt_deg=10)
    r = solar.estimate_solar("b1", 29.76, -95.37, 200, tilt_deg=10)
    assert r.annual_kwh == 2000.0


def test_retries_after_429_then_succeeds(calls):
    calls["responses"] = [FakeResponse(429), FakeResponse(429), ok(500.0)]
    r = solar.estimate_solar("b1", 29.76, -95.37, 100, tilt_deg=10)
    assert r.annual_kwh == 500.0
    assert len(calls["params"]) == 3


def test_gives_up_after_repeated_429(calls):
    calls["responses"] = [FakeResponse(429)] * solar.MAX_ATTEMPTS
    with pytest.raises(solar.requests.HTTPError):
        solar.estimate_solar("b1", 29.76, -95.37, 100, tilt_deg=10)


def test_api_error_list_raises(calls):
    calls["responses"] = [FakeResponse(200, {"errors": ["tilt must be between 0 and 90"]})]
    with pytest.raises(RuntimeError, match="tilt"):
        solar.estimate_solar("b1", 29.76, -95.37, 100, tilt_deg=95)


def test_missing_api_key_raises_clear_error(calls, monkeypatch):
    monkeypatch.delenv("NLR_API_KEY")
    with pytest.raises(RuntimeError, match="NLR_API_KEY"):
        solar.estimate_solar("b1", 29.76, -95.37, 100, tilt_deg=10)
