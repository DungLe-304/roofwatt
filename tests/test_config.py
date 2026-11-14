"""config.py wiring: settings are read from the repo root, not from outside the repo."""

from pathlib import Path

import pytest

import config

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_path_is_repo_root():
	assert config.rootPath == REPO_ROOT


def test_load_settings_reads_repo_env(tmp_path, monkeypatch):
	(tmp_path / ".env").write_text("pvwattsApiKey=from-env-file\n")
	monkeypatch.setattr(config, "rootPath", tmp_path)
	monkeypatch.delenv("pvwattsApiKey", raising=False)
	assert config.loadSettings().pvwattsApiKey.get_secret_value() == "from-env-file"


def test_default_model_is_gemini():
	assert config.Settings().modelName == "google_genai:gemini-4-hydrogen"
	assert "anthropicApiKey" not in config.Settings.model_fields


def test_live_agent_requires_google_api_key(tmp_path, monkeypatch):
	(tmp_path / ".env").write_text("agentMode=live\n")
	monkeypatch.setattr(config, "rootPath", tmp_path)
	monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
	with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
		config.loadSettings()
	monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
	assert config.loadSettings().agentMode == "live"
