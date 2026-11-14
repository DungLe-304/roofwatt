"""config.py wiring: settings are read from the repo root, not from outside the repo."""

from pathlib import Path

import config

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_path_is_repo_root():
	assert config.rootPath == REPO_ROOT


def test_load_settings_reads_repo_env(tmp_path, monkeypatch):
	(tmp_path / ".env").write_text("pvwattsApiKey=from-env-file\n")
	monkeypatch.setattr(config, "rootPath", tmp_path)
	monkeypatch.delenv("pvwattsApiKey", raising=False)
	assert config.loadSettings().pvwattsApiKey.get_secret_value() == "from-env-file"
