"""Tests for the CLI."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from unfold.cli.main import main


@pytest.fixture
def cli_runner():
    """Create a Click CLI runner."""
    return CliRunner()


def test_help_output(cli_runner):
    """Test --help output."""
    result = cli_runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "unfold" in result.output
    assert "BINARY" in result.output
    assert "--mode" in result.output
    assert "--goal" in result.output


def test_list_sessions_flag(cli_runner):
    """Test --list-sessions flag."""
    with patch("unfold.session.list_sessions") as mock_list:
        result = cli_runner.invoke(main, ["--list-sessions"])

        assert result.exit_code == 0
        mock_list.assert_called_once()


def test_missing_binary_argument(cli_runner):
    """Test missing binary argument gives error."""
    result = cli_runner.invoke(main, [])

    assert result.exit_code != 0
    assert "Missing argument" in result.output or "BINARY" in result.output


def test_nonexistent_binary_path(cli_runner):
    """Test nonexistent binary path gives error."""
    result = cli_runner.invoke(main, ["/nonexistent/binary"])

    # Should fail because file doesn't exist
    assert result.exit_code != 0


def test_valid_binary_with_mocked_agent(cli_runner, tmp_binary, monkeypatch):
    """Test valid binary argument with mocked Agent."""
    # Mock _ensure_ghidra_started
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    # Mock GhidraBridge.__init__
    from pathlib import Path

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    # Mock Agent.run to avoid actual analysis
    def mock_run(self, goal=None):
        return "Mocked analysis complete."

    monkeypatch.setattr("unfold.agent.core.Agent.run", mock_run)

    # Mock anthropic.Anthropic
    with patch("anthropic.Anthropic"):
        result = cli_runner.invoke(main, [str(tmp_binary)])

        # Should succeed (exit code 0)
        assert result.exit_code == 0
        assert "unfold" in result.output.lower()


def test_mode_flag(cli_runner, tmp_binary, monkeypatch):
    """Test --mode flag."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    from pathlib import Path

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    def mock_run(self, goal=None):
        return "Analysis complete."

    monkeypatch.setattr("unfold.agent.core.Agent.run", mock_run)

    with patch("anthropic.Anthropic"):
        result = cli_runner.invoke(main, [str(tmp_binary), "--mode", "ctf"])

        assert result.exit_code == 0


def test_goal_flag(cli_runner, tmp_binary, monkeypatch):
    """Test --goal flag."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    from pathlib import Path

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    captured_goal = None

    def mock_run(self, goal=None):
        nonlocal captured_goal
        captured_goal = goal
        return "Analysis complete."

    monkeypatch.setattr("unfold.agent.core.Agent.run", mock_run)

    with patch("anthropic.Anthropic"):
        result = cli_runner.invoke(main, [str(tmp_binary), "--goal", "find the flag"])

        assert result.exit_code == 0
        assert captured_goal == "find the flag"


def test_output_flag(cli_runner, tmp_binary, tmp_path, monkeypatch):
    """Test --output flag saves report."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    from pathlib import Path

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    def mock_run(self, goal=None):
        return "Analysis complete."

    monkeypatch.setattr("unfold.agent.core.Agent.run", mock_run)

    output_file = tmp_path / "report.md"

    with patch("anthropic.Anthropic"):
        result = cli_runner.invoke(main, [str(tmp_binary), "--output", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()


def test_format_json_flag(cli_runner, tmp_binary, tmp_path, monkeypatch):
    """Test --format json flag."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    from pathlib import Path

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    def mock_run(self, goal=None):
        return "Analysis complete."

    monkeypatch.setattr("unfold.agent.core.Agent.run", mock_run)

    output_file = tmp_path / "report.json"

    with patch("anthropic.Anthropic"):
        result = cli_runner.invoke(
            main, [str(tmp_binary), "--output", str(output_file), "--format", "json"]
        )

        assert result.exit_code == 0
        assert output_file.exists()

        # Check it's valid JSON
        import json

        content = json.loads(output_file.read_text())
        assert "version" in content


def test_resume_flag(cli_runner, tmp_binary, tmp_path, monkeypatch):
    """Test --resume flag."""
    import json

    session_file = tmp_path / "session.json"
    session_data = {
        "version": "0.2.0",
        "binary_path": str(tmp_binary),
        "mode": "explore",
        "model": "claude-sonnet-4-5-20250929",
        "max_turns": 50,
        "stream": False,
        "messages": [],
        "turn_data": [],
        "usage": {},
    }
    session_file.write_text(json.dumps(session_data))

    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    from pathlib import Path

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    with patch("anthropic.Anthropic"):
        result = cli_runner.invoke(main, ["--resume", str(session_file)])

        assert result.exit_code == 0
        assert "Resuming" in result.output


def test_interactive_flag_basic(cli_runner, tmp_binary, monkeypatch):
    """Test --interactive flag starts REPL (basic check)."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    from pathlib import Path

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    def mock_run(self, goal=None):
        return "Analysis complete."

    monkeypatch.setattr("unfold.agent.core.Agent.run", mock_run)

    with patch("anthropic.Anthropic"):
        # Simulate user typing 'quit' immediately
        result = cli_runner.invoke(main, [str(tmp_binary), "-i"], input="quit\n")

        assert result.exit_code == 0
        assert "interactive" in result.output.lower() or ">" in result.output


def test_stream_flag(cli_runner, tmp_binary, monkeypatch):
    """Test --stream flag."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    from pathlib import Path

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    captured_stream = None

    def mock_agent_init(
        self,
        binary_path,
        mode="explore",
        model=None,
        max_turns=None,
        project_dir=None,
        config=None,
        stream=None,
    ):
        nonlocal captured_stream
        captured_stream = stream

    monkeypatch.setattr("unfold.agent.core.Agent.__init__", mock_agent_init)

    def mock_run(self, goal=None):
        return "Analysis complete."

    monkeypatch.setattr("unfold.agent.core.Agent.run", mock_run)

    with patch("anthropic.Anthropic"):
        cli_runner.invoke(main, [str(tmp_binary), "--stream"])

        # Should have set stream=True
        assert captured_stream is True


def test_no_stream_flag(cli_runner, tmp_binary, monkeypatch):
    """Test --no-stream flag."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    from pathlib import Path

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    captured_stream = None

    def mock_agent_init(
        self,
        binary_path,
        mode="explore",
        model=None,
        max_turns=None,
        project_dir=None,
        config=None,
        stream=None,
    ):
        nonlocal captured_stream
        captured_stream = stream

    monkeypatch.setattr("unfold.agent.core.Agent.__init__", mock_agent_init)

    def mock_run(self, goal=None):
        return "Analysis complete."

    monkeypatch.setattr("unfold.agent.core.Agent.run", mock_run)

    with patch("anthropic.Anthropic"):
        cli_runner.invoke(main, [str(tmp_binary), "--no-stream"])

        # Should have set stream=False
        assert captured_stream is False
