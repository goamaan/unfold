"""Configuration system for unfold.

Resolution order: CLI flags > env vars > .unfold.toml (CWD) > ~/.config/unfold/config.toml > defaults
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

from unfold.errors import ConfigError


@dataclass
class Config:
    """Central configuration for unfold."""

    model: str = "claude-sonnet-4-5-20250929"
    max_turns: int = 50
    max_tokens: int = 16384
    truncation_limit: int = 30000
    mode_models: dict[str, str] = field(default_factory=dict)
    ghidra_install_dir: str | None = None
    java_home: str | None = None
    project_dir: str = "~/.unfold/projects"
    output_format: str = "terminal"
    output_file: str | None = None
    stream: bool = True
    save_session: bool = False

    @property
    def resolved_project_dir(self) -> Path:
        """Return project_dir as an expanded absolute Path."""
        return Path(self.project_dir).expanduser().resolve()

    def model_for_mode(self, mode: str) -> str:
        """Return the model to use for a given analysis mode."""
        return self.mode_models.get(mode, self.model)


def load_config(
    cli_overrides: dict | None = None,
) -> Config:
    """Load config with resolution order: CLI > env > .unfold.toml > ~/.config/unfold/config.toml > defaults.

    Args:
        cli_overrides: Dict of CLI flag values (None values are ignored).

    Returns:
        Merged Config instance.
    """
    config = Config()

    # Layer 1: Config files (lowest priority)
    file_values = _load_config_files()
    _apply_dict(config, file_values)

    # Layer 2: Environment variables
    env_values = _load_env_vars()
    _apply_dict(config, env_values)

    # Layer 3: CLI overrides (highest priority)
    if cli_overrides:
        _apply_dict(config, cli_overrides)

    return config


def _load_config_files() -> dict:
    """Load config from TOML files. CWD file takes precedence over global."""
    values: dict = {}

    # Global config (lower priority)
    global_path = Path.home() / ".config" / "unfold" / "config.toml"
    if global_path.exists():
        values.update(_parse_toml(global_path))

    # CWD config (higher priority — overwrites global)
    local_path = Path.cwd() / ".unfold.toml"
    if local_path.exists():
        values.update(_parse_toml(local_path))

    return values


def _parse_toml(path: Path) -> dict:
    """Parse a TOML config file, returning a flat dict of config values."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        raise ConfigError(f"Failed to parse config file {path}: {e}") from e

    # Flatten: top-level keys map directly to Config fields
    # Nested tables like [mode_models] become dicts
    result: dict = {}
    for key, value in data.items():
        if key == "mode_models" and isinstance(value, dict):
            result["mode_models"] = dict(value)
        elif hasattr(Config, key):
            result[key] = value

    return result


def _load_env_vars() -> dict:
    """Load config from environment variables."""
    values: dict = {}

    env_map = {
        "UNFOLD_MODEL": "model",
        "UNFOLD_MAX_TURNS": ("max_turns", int),
        "UNFOLD_MAX_TOKENS": ("max_tokens", int),
        "UNFOLD_TRUNCATION_LIMIT": ("truncation_limit", int),
        "GHIDRA_INSTALL_DIR": "ghidra_install_dir",
        "JAVA_HOME": "java_home",
        "UNFOLD_PROJECT_DIR": "project_dir",
        "UNFOLD_OUTPUT_FORMAT": "output_format",
        "UNFOLD_OUTPUT_FILE": "output_file",
    }

    for env_key, mapping in env_map.items():
        raw = os.environ.get(env_key)
        if raw is None:
            continue

        if isinstance(mapping, tuple):
            field_name, converter = mapping
            try:
                values[field_name] = converter(raw)
            except (ValueError, TypeError) as e:
                raise ConfigError(f"Invalid value for {env_key}={raw!r}: {e}") from e
        else:
            values[mapping] = raw

    return values


def _apply_dict(config: Config, values: dict) -> None:
    """Apply a dict of values onto a Config, ignoring None values and unknown keys."""
    for key, value in values.items():
        if value is None:
            continue
        if hasattr(config, key):
            setattr(config, key, value)
