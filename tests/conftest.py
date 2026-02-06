"""Common fixtures for unfold tests."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from unfold.config import Config


@pytest.fixture
def mock_config():
    """A Config with test defaults."""
    return Config(
        model="claude-sonnet-4-5-20250929",
        max_turns=10,
        max_tokens=8192,
        truncation_limit=10000,
        mode_models={},
        ghidra_install_dir=None,
        java_home=None,
        project_dir="/tmp/unfold_test_projects",
        output_format="terminal",
        output_file=None,
        stream=False,
        save_session=False,
    )


@pytest.fixture
def tmp_binary(tmp_path):
    """Create a small temp file to use as a binary path."""
    binary = tmp_path / "test_binary"
    binary.write_bytes(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56)
    return binary


@pytest.fixture
def mock_bridge(monkeypatch):
    """A mock GhidraBridge that returns canned data without JVM."""
    from tests.fixtures import mock_data

    mock_bridge_instance = MagicMock()

    # Mock all GhidraBridge methods with canned responses
    mock_bridge_instance.analyze.return_value = mock_data.ANALYZE_RESULT
    mock_bridge_instance.list_functions.return_value = mock_data.FUNCTIONS_LIST
    mock_bridge_instance.decompile.return_value = mock_data.DECOMPILE_RESULT
    mock_bridge_instance.get_xrefs_to.return_value = mock_data.XREFS_TO_RESULT
    mock_bridge_instance.get_xrefs_from.return_value = mock_data.XREFS_FROM_RESULT
    mock_bridge_instance.get_strings.return_value = mock_data.STRINGS_RESULT
    mock_bridge_instance.get_imports_exports.return_value = mock_data.IMPORTS_EXPORTS_RESULT
    mock_bridge_instance.rename_function.return_value = mock_data.RENAME_RESULT
    mock_bridge_instance.read_bytes.return_value = mock_data.READ_BYTES_RESULT

    # Patch _ensure_ghidra_started to be a no-op
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    # Patch GhidraBridge.__init__ to skip JVM initialization
    def mock_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_init)

    return mock_bridge_instance


@pytest.fixture
def mock_anthropic_response():
    """Factory fixture that creates mock Anthropic API responses."""

    def _make_response(
        content_text: str = "Analysis complete.",
        stop_reason: str = "end_turn",
        input_tokens: int = 100,
        output_tokens: int = 50,
        tool_use: list | None = None,
    ):
        """Create a mock Anthropic response.

        Args:
            content_text: Text content for the response
            stop_reason: Stop reason (end_turn, tool_use, max_tokens)
            input_tokens: Input token count for usage
            output_tokens: Output token count for usage
            tool_use: List of tool use dicts (e.g., [{"name": "analyze_binary", "id": "1", "input": {}}])
        """
        # Create content blocks
        content_blocks = []

        if content_text:
            text_block = MagicMock()
            text_block.type = "text"
            text_block.text = content_text
            content_blocks.append(text_block)

        if tool_use:
            for tool in tool_use:
                tool_block = MagicMock()
                tool_block.type = "tool_use"
                tool_block.id = tool.get("id", "tool_1")
                tool_block.name = tool.get("name", "analyze_binary")
                tool_block.input = tool.get("input", {})
                content_blocks.append(tool_block)

        # Create usage object
        usage = MagicMock()
        usage.input_tokens = input_tokens
        usage.output_tokens = output_tokens

        # Create response object
        response = MagicMock()
        response.content = content_blocks
        response.stop_reason = stop_reason
        response.usage = usage

        return response

    return _make_response


@pytest.fixture
def mock_openai_response():
    """Factory fixture that creates mock OpenAI API responses."""

    def _make_response(
        content_text: str = "Analysis complete.",
        finish_reason: str = "stop",
        prompt_tokens: int = 100,
        completion_tokens: int = 50,
        tool_calls: list | None = None,
    ):
        """Create a mock OpenAI response.

        Args:
            content_text: Text content for the response
            finish_reason: Finish reason (stop, tool_calls, length)
            prompt_tokens: Prompt token count for usage
            completion_tokens: Completion token count for usage
            tool_calls: List of tool call dicts
        """
        # Create message
        message = MagicMock()
        message.content = content_text
        message.tool_calls = tool_calls

        # Create choice
        choice = MagicMock()
        choice.message = message
        choice.finish_reason = finish_reason

        # Create usage
        usage = MagicMock()
        usage.prompt_tokens = prompt_tokens
        usage.completion_tokens = completion_tokens

        # Create response
        response = MagicMock()
        response.choices = [choice]
        response.usage = usage

        return response

    return _make_response
