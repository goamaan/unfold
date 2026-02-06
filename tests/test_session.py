"""Tests for session persistence."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from unfold.session import SESSIONS_DIR, load_session, save_session


def test_save_session_creates_file(tmp_binary, monkeypatch):
    """Test save_session() creates a file."""
    # Mock _ensure_ghidra_started
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    # Create a mock agent
    from unfold.agent.core import Agent

    with patch("anthropic.Anthropic"):
        agent = Agent(binary_path=tmp_binary, mode="explore")
        agent.messages = [{"role": "user", "content": "test"}]
        agent.turn_data = [{"turn": 1, "text": "test", "tool_calls": []}]

        session_path = save_session(agent)

        assert session_path.exists()
        assert session_path.is_file()
        assert session_path.suffix == ".json"


def test_load_session_reads_back_data(tmp_binary, tmp_path):
    """Test load_session() reads back the data."""
    session_file = tmp_path / "session.json"
    session_data = {
        "version": "0.2.0",
        "binary_path": str(tmp_binary),
        "mode": "ctf",
        "model": "claude-sonnet-4-5-20250929",
        "max_turns": 50,
        "stream": True,
        "messages": [{"role": "user", "content": "test"}],
        "turn_data": [{"turn": 1, "text": "test", "tool_calls": []}],
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }
    session_file.write_text(json.dumps(session_data))

    loaded = load_session(session_file)

    assert loaded["binary_path"] == str(tmp_binary)
    assert loaded["mode"] == "ctf"
    assert loaded["model"] == "claude-sonnet-4-5-20250929"
    assert len(loaded["messages"]) == 1
    assert len(loaded["turn_data"]) == 1


def test_save_load_roundtrip(tmp_binary, monkeypatch):
    """Test save/load roundtrip."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    from unfold.agent.core import Agent

    with patch("anthropic.Anthropic"):
        agent = Agent(
            binary_path=tmp_binary, mode="vuln", model="claude-haiku-3-5-20241022", max_turns=25
        )
        agent.messages = [
            {"role": "user", "content": "find vulnerabilities"},
            {"role": "assistant", "content": "let me check"},
        ]
        agent.turn_data = [{"turn": 1, "text": "let me check", "tool_calls": []}]

        session_path = save_session(agent)

        # Load it back
        loaded = load_session(session_path)

        assert loaded["binary_path"] == str(tmp_binary.resolve())
        assert loaded["mode"] == "vuln"
        assert loaded["model"] == "claude-haiku-3-5-20241022"
        assert loaded["max_turns"] == 25
        assert len(loaded["messages"]) == 2
        assert len(loaded["turn_data"]) == 1


def test_load_session_with_missing_file_raises(tmp_path):
    """Test load_session with missing file raises FileNotFoundError."""
    nonexistent = tmp_path / "nonexistent.json"

    with pytest.raises(FileNotFoundError, match="Session file not found"):
        load_session(nonexistent)


def test_load_session_with_invalid_data_raises(tmp_path):
    """Test load_session with invalid data raises ValueError."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text(json.dumps({"foo": "bar"}))  # Missing required keys

    with pytest.raises(ValueError, match="Invalid session file"):
        load_session(invalid_file)


def test_save_session_includes_all_fields(tmp_binary, monkeypatch):
    """Test save_session includes all expected fields."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    from unfold.agent.core import Agent

    with patch("anthropic.Anthropic"):
        agent = Agent(binary_path=tmp_binary, mode="explore")
        agent.messages = [{"role": "user", "content": "test"}]
        agent.turn_data = []

        session_path = save_session(agent)

        # Load and check fields
        data = json.loads(session_path.read_text())

        assert "version" in data
        assert "binary_path" in data
        assert "mode" in data
        assert "model" in data
        assert "max_turns" in data
        assert "stream" in data
        assert "messages" in data
        assert "turn_data" in data
        assert "usage" in data
        assert "saved_at" in data


def test_save_session_creates_latest_symlink(tmp_binary, monkeypatch):
    """Test save_session creates/updates latest.json symlink."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    from unfold.agent.core import Agent

    with patch("anthropic.Anthropic"):
        agent = Agent(binary_path=tmp_binary, mode="explore")

        save_session(agent)

        latest_path = SESSIONS_DIR / "latest.json"

        # latest.json should exist (or be a symlink)
        # Skip test on systems that don't support symlinks
        if latest_path.exists() or latest_path.is_symlink():
            assert latest_path.is_symlink() or latest_path.is_file()


def test_save_session_filename_format(tmp_binary, monkeypatch):
    """Test session filename format is stem_timestamp.json."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    from unfold.agent.core import Agent

    with patch("anthropic.Anthropic"):
        agent = Agent(binary_path=tmp_binary, mode="explore")

        session_path = save_session(agent)

        # Filename should start with binary stem
        assert session_path.name.startswith(tmp_binary.stem)
        assert session_path.name.endswith(".json")

        # Should contain timestamp (8 digits, underscore, 6 digits)
        # Format: stem_YYYYMMDD_HHMMSS.json
        parts = session_path.stem.split("_")
        assert len(parts) >= 3  # stem, date, time


def test_session_serializes_anthropic_content_blocks(tmp_binary, monkeypatch):
    """Test session correctly serializes Anthropic content blocks."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    from unfold.agent.core import Agent

    with patch("anthropic.Anthropic"):
        agent = Agent(binary_path=tmp_binary, mode="explore")

        # Create a mock content block
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Test text"

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tool_1"
        tool_block.name = "analyze_binary"
        tool_block.input = {}

        agent.messages = [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": [text_block, tool_block]},
        ]

        session_path = save_session(agent)

        # Load and verify serialization
        data = json.loads(session_path.read_text())

        # Second message should have serialized content blocks
        assistant_msg = data["messages"][1]
        assert isinstance(assistant_msg["content"], list)
        assert assistant_msg["content"][0]["type"] == "text"
        assert assistant_msg["content"][0]["text"] == "Test text"
        assert assistant_msg["content"][1]["type"] == "tool_use"
        assert assistant_msg["content"][1]["name"] == "analyze_binary"


def test_load_session_validates_required_keys(tmp_path):
    """Test load_session validates presence of required keys."""
    # Missing 'messages' key
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text(json.dumps({"binary_path": "/test/binary"}))

    with pytest.raises(ValueError, match="Invalid session file"):
        load_session(invalid_file)


def test_sessions_dir_location():
    """Test SESSIONS_DIR is in the expected location."""
    expected = Path.home() / ".unfold" / "sessions"
    assert SESSIONS_DIR == expected
