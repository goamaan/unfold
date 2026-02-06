"""Tests for the Agent class."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from unfold.agent.core import Agent
from unfold.config import Config


@pytest.fixture
def mock_ghidra_completely(monkeypatch):
    """Mock GhidraBridge completely to avoid any JVM operations."""
    # Patch _ensure_ghidra_started to be a no-op
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    # Patch GhidraBridge.__init__ to skip JVM initialization
    def mock_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_init)


def test_agent_init_sets_up_correctly(mock_ghidra_completely, tmp_binary, mock_config):
    """Test Agent.__init__ sets up correctly."""
    with patch("anthropic.Anthropic"):
        agent = Agent(
            binary_path=tmp_binary,
            mode="explore",
            model="claude-sonnet-4-5-20250929",
            max_turns=10,
            config=mock_config,
        )

        assert agent.binary_path == tmp_binary.resolve()
        assert agent.mode == "explore"
        assert agent.model == "claude-sonnet-4-5-20250929"
        assert agent.max_turns == 10
        assert agent.messages == []
        assert agent.turn_data == []
        assert agent.usage.model == "claude-sonnet-4-5-20250929"


def test_agent_init_raises_if_binary_not_found(mock_ghidra_completely, tmp_path):
    """Test Agent.__init__ raises FileNotFoundError if binary doesn't exist."""
    nonexistent_binary = tmp_path / "nonexistent"

    with patch("anthropic.Anthropic"):
        with pytest.raises(FileNotFoundError, match="Binary not found"):
            Agent(
                binary_path=nonexistent_binary,
                mode="explore",
            )


def test_agent_run_with_mocked_anthropic(
    mock_ghidra_completely, tmp_binary, mock_config, mock_anthropic_response, monkeypatch
):
    """Test Agent.run() with mocked 2-turn simulation."""
    from tests.fixtures import mock_data

    # Mock anthropic.Anthropic
    mock_client = MagicMock()

    # Turn 1: Tool call
    response1 = mock_anthropic_response(
        content_text="Let me analyze the binary.",
        stop_reason="tool_use",
        tool_use=[{"name": "analyze_binary", "id": "tool_1", "input": {}}],
    )

    # Turn 2: End turn
    response2 = mock_anthropic_response(
        content_text="Analysis complete. The binary is a Mach-O executable.",
        stop_reason="end_turn",
    )

    mock_client.messages.create.side_effect = [response1, response2]

    with patch("anthropic.Anthropic", return_value=mock_client):
        # Mock execute_tool to return canned data
        def mock_execute_tool(handler_map, tool_name, tool_input):
            if tool_name == "analyze_binary":
                return json.dumps(mock_data.ANALYZE_RESULT)
            return json.dumps({"error": "Unknown tool"})

        monkeypatch.setattr("unfold.agent.core.execute_tool", mock_execute_tool)

        agent = Agent(
            binary_path=tmp_binary,
            mode="explore",
            config=mock_config,
            stream=False,
        )

        result = agent.run()

        # Check that run completed
        assert "complete" in result.lower() or "mach-o" in result.lower()

        # Check that two turns occurred
        assert len(agent.turn_data) == 2

        # Check first turn had tool call
        assert len(agent.turn_data[0]["tool_calls"]) == 1
        assert agent.turn_data[0]["tool_calls"][0]["name"] == "analyze_binary"

        # Check messages were accumulated
        assert len(agent.messages) > 0


def test_agent_usage_tracking_after_run(
    mock_ghidra_completely, tmp_binary, mock_config, mock_anthropic_response
):
    """Test that usage tracking is populated after run."""
    mock_client = MagicMock()

    response = mock_anthropic_response(
        content_text="Analysis complete.",
        stop_reason="end_turn",
        input_tokens=150,
        output_tokens=75,
    )

    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        agent = Agent(
            binary_path=tmp_binary,
            mode="explore",
            config=mock_config,
            stream=False,
        )

        agent.run()

        # Check usage was tracked
        assert agent.usage.input_tokens == 150
        assert agent.usage.output_tokens == 75
        assert agent.usage.api_calls == 1


def test_agent_from_session(mock_ghidra_completely, tmp_binary, tmp_path, mock_config):
    """Test Agent.from_session classmethod."""
    session_data = {
        "version": "0.2.0",
        "binary_path": str(tmp_binary),
        "mode": "ctf",
        "model": "claude-opus-4-5-20250514",
        "max_turns": 25,
        "stream": True,
        "messages": [
            {"role": "user", "content": "Analyze this binary"},
            {"role": "assistant", "content": "Let me check..."},
        ],
        "turn_data": [{"turn": 1, "text": "Let me check...", "tool_calls": []}],
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }

    session_file = tmp_path / "session.json"
    session_file.write_text(json.dumps(session_data))

    with patch("anthropic.Anthropic"):
        agent = Agent.from_session(session_file, config=mock_config)

        assert agent.binary_path == tmp_binary.resolve()
        assert agent.mode == "ctf"
        assert agent.model == "claude-opus-4-5-20250514"
        assert agent.max_turns == 25
        assert agent.stream is True
        assert len(agent.messages) == 2
        assert len(agent.turn_data) == 1


def test_agent_from_session_raises_if_binary_missing(mock_ghidra_completely, tmp_path, mock_config):
    """Test Agent.from_session raises if binary no longer exists."""
    session_data = {
        "version": "0.2.0",
        "binary_path": "/nonexistent/binary",
        "mode": "explore",
        "messages": [],
        "turn_data": [],
    }

    session_file = tmp_path / "session.json"
    session_file.write_text(json.dumps(session_data))

    with patch("anthropic.Anthropic"):
        with pytest.raises(FileNotFoundError, match="Binary from session not found"):
            Agent.from_session(session_file, config=mock_config)


def test_agent_detects_openai_backend(mock_ghidra_completely, tmp_binary, mock_config, monkeypatch):
    """Test Agent detects OpenAI-compatible backend when env vars are set."""
    monkeypatch.setenv("CLIPROXY_BASE_URL", "https://proxy.example.com")
    monkeypatch.setenv("CLIPROXY_API_KEY", "test-key")

    with patch("openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        agent = Agent(
            binary_path=tmp_binary,
            mode="explore",
            config=mock_config,
        )

        assert agent._backend == "openai"
        mock_openai_class.assert_called_once_with(
            base_url="https://proxy.example.com", api_key="test-key"
        )


def test_agent_uses_anthropic_backend_by_default(mock_ghidra_completely, tmp_binary, mock_config):
    """Test Agent uses Anthropic backend when no proxy env vars are set."""
    with patch("anthropic.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        agent = Agent(
            binary_path=tmp_binary,
            mode="explore",
            config=mock_config,
        )

        assert agent._backend == "anthropic"
        mock_anthropic_class.assert_called_once_with(max_retries=3)


def test_agent_model_resolution_order(mock_ghidra_completely, tmp_binary):
    """Test model resolution: explicit arg > mode_models > config default."""
    config = Config(
        model="default-model",
        mode_models={"ctf": "ctf-model"},
    )

    with patch("anthropic.Anthropic"):
        # Explicit model wins
        agent1 = Agent(binary_path=tmp_binary, mode="ctf", model="explicit-model", config=config)
        assert agent1.model == "explicit-model"

        # Mode model wins over default
        agent2 = Agent(binary_path=tmp_binary, mode="ctf", config=config)
        assert agent2.model == "ctf-model"

        # Default when no mode model
        agent3 = Agent(binary_path=tmp_binary, mode="explore", config=config)
        assert agent3.model == "default-model"


def test_agent_truncate_method(mock_ghidra_completely, tmp_binary, mock_config):
    """Test Agent._truncate method."""
    with patch("anthropic.Anthropic"):
        agent = Agent(
            binary_path=tmp_binary,
            mode="explore",
            config=mock_config,
        )

        short_text = "short"
        assert agent._truncate(short_text) == "short"

        long_text = "x" * 15000
        truncated = agent._truncate(long_text)
        assert len(truncated) <= mock_config.truncation_limit + 20  # +20 for "... (truncated)"
        assert "... (truncated)" in truncated


def test_agent_ask_continues_conversation(
    mock_ghidra_completely, tmp_binary, mock_config, mock_anthropic_response, monkeypatch
):
    """Test Agent.ask() continues the conversation."""
    mock_client = MagicMock()

    response = mock_anthropic_response(
        content_text="Here's the answer to your question.",
        stop_reason="end_turn",
    )

    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        agent = Agent(
            binary_path=tmp_binary,
            mode="explore",
            config=mock_config,
            stream=False,
        )

        # Simulate initial run
        agent.messages = [
            {"role": "user", "content": "Analyze this binary"},
            {"role": "assistant", "content": "Analysis complete."},
        ]

        # Ask a follow-up question
        result = agent.ask("What about the strings?")

        assert "answer" in result.lower() or len(result) > 0
        assert len(agent.messages) == 4  # Original 2 + question + response
