"""Tests for the Config system."""

import os
from pathlib import Path

import pytest

from unfold.config import Config, load_config
from unfold.errors import ConfigError


def test_default_values():
    """Test Config has correct default values."""
    config = Config()
    assert config.model == "claude-sonnet-4-5-20250929"
    assert config.max_turns == 50
    assert config.max_tokens == 16384
    assert config.truncation_limit == 30000
    assert config.mode_models == {}
    assert config.project_dir == "~/.unfold/projects"
    assert config.output_format == "terminal"
    assert config.output_file is None
    assert config.stream is True
    assert config.save_session is False


def test_resolved_project_dir():
    """Test resolved_project_dir expands paths correctly."""
    config = Config(project_dir="~/test_projects")
    resolved = config.resolved_project_dir
    assert isinstance(resolved, Path)
    assert resolved.is_absolute()
    assert "~" not in str(resolved)


def test_model_for_mode():
    """Test model_for_mode returns correct model."""
    config = Config(
        model="claude-sonnet-4-5-20250929",
        mode_models={"ctf": "claude-opus-4-5-20250514", "vuln": "claude-haiku-3-5-20241022"},
    )
    assert config.model_for_mode("explore") == "claude-sonnet-4-5-20250929"
    assert config.model_for_mode("ctf") == "claude-opus-4-5-20250514"
    assert config.model_for_mode("vuln") == "claude-haiku-3-5-20241022"


def test_load_from_toml_file(tmp_path):
    """Test loading config from TOML file."""
    config_file = tmp_path / ".unfold.toml"
    config_file.write_text(
        """
model = "claude-opus-4-5-20250514"
max_turns = 100
max_tokens = 32768
truncation_limit = 50000
project_dir = "/custom/path"

[mode_models]
ctf = "claude-sonnet-4-5-20250929"
vuln = "claude-haiku-3-5-20241022"
"""
    )

    # Change to temp dir so load_config finds .unfold.toml
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        config = load_config()

        assert config.model == "claude-opus-4-5-20250514"
        assert config.max_turns == 100
        assert config.max_tokens == 32768
        assert config.truncation_limit == 50000
        assert config.project_dir == "/custom/path"
        assert config.mode_models == {
            "ctf": "claude-sonnet-4-5-20250929",
            "vuln": "claude-haiku-3-5-20241022",
        }
    finally:
        os.chdir(original_cwd)


def test_env_var_overrides(monkeypatch):
    """Test environment variable overrides."""
    monkeypatch.setenv("UNFOLD_MODEL", "claude-haiku-3-5-20241022")
    monkeypatch.setenv("UNFOLD_MAX_TURNS", "200")
    monkeypatch.setenv("UNFOLD_MAX_TOKENS", "8192")
    monkeypatch.setenv("UNFOLD_TRUNCATION_LIMIT", "15000")
    monkeypatch.setenv("UNFOLD_PROJECT_DIR", "/env/projects")

    config = load_config()

    assert config.model == "claude-haiku-3-5-20241022"
    assert config.max_turns == 200
    assert config.max_tokens == 8192
    assert config.truncation_limit == 15000
    assert config.project_dir == "/env/projects"


def test_cli_overrides_take_priority(monkeypatch):
    """Test CLI overrides have highest priority."""
    monkeypatch.setenv("UNFOLD_MODEL", "claude-haiku-3-5-20241022")
    monkeypatch.setenv("UNFOLD_MAX_TURNS", "200")

    cli_overrides = {
        "model": "claude-opus-4-5-20250514",
        "max_turns": 25,
    }

    config = load_config(cli_overrides=cli_overrides)

    assert config.model == "claude-opus-4-5-20250514"  # CLI wins
    assert config.max_turns == 25  # CLI wins


def test_resolution_order(tmp_path, monkeypatch):
    """Test full resolution order: CLI > env > file > defaults."""
    # Create TOML file
    config_file = tmp_path / ".unfold.toml"
    config_file.write_text('model = "file-model"\nmax_turns = 75\n')

    # Set env var
    monkeypatch.setenv("UNFOLD_MODEL", "env-model")
    monkeypatch.setenv("UNFOLD_TRUNCATION_LIMIT", "20000")

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        # CLI override for model only
        config = load_config(cli_overrides={"model": "cli-model"})

        assert config.model == "cli-model"  # CLI wins
        assert config.max_turns == 75  # From file (env doesn't have this)
        assert config.truncation_limit == 20000  # From env
        assert config.max_tokens == 16384  # Default (not overridden)
    finally:
        os.chdir(original_cwd)


def test_invalid_env_var_raises_config_error(monkeypatch):
    """Test invalid env var values raise ConfigError."""
    monkeypatch.setenv("UNFOLD_MAX_TURNS", "not-a-number")

    with pytest.raises(ConfigError, match="Invalid value for UNFOLD_MAX_TURNS"):
        load_config()


def test_invalid_toml_raises_config_error(tmp_path):
    """Test invalid TOML file raises ConfigError."""
    config_file = tmp_path / ".unfold.toml"
    config_file.write_text("invalid toml syntax {{{")

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        with pytest.raises(ConfigError, match="Failed to parse config file"):
            load_config()
    finally:
        os.chdir(original_cwd)


def test_none_values_in_cli_overrides_are_ignored():
    """Test that None values in CLI overrides don't override config."""
    config = load_config(cli_overrides={"model": None, "max_turns": 25})

    assert config.model == "claude-sonnet-4-5-20250929"  # Default (None ignored)
    assert config.max_turns == 25  # Applied
