"""Tests for report generation."""

import json

from unfold.report import AnalysisInfo, BinaryInfo, Report


def test_report_to_json_produces_valid_json():
    """Test Report.to_json() produces valid JSON."""
    report = Report(
        version="0.2.0",
        binary=BinaryInfo(name="test", path="/test/binary", sha256="abc123", architecture="x86"),
        analysis=AnalysisInfo(
            mode="explore",
            model="claude-sonnet-4-5-20250929",
            goal="test",
            started_at="2024-01-01",
            completed_at="2024-01-01",
        ),
        summary="Test summary",
        turns=[{"turn": 1, "text": "Test", "tool_calls": []}],
        usage={"input_tokens": 100, "output_tokens": 50},
    )

    json_output = report.to_json()

    # Should be valid JSON
    parsed = json.loads(json_output)
    assert parsed["version"] == "0.2.0"
    assert parsed["binary"]["name"] == "test"
    assert parsed["summary"] == "Test summary"


def test_report_to_markdown_produces_markdown():
    """Test Report.to_markdown() produces Markdown with expected sections."""
    report = Report(
        version="0.2.0",
        binary=BinaryInfo(name="test", path="/test/binary", sha256="abc123", architecture="x86"),
        analysis=AnalysisInfo(
            mode="explore",
            model="claude-sonnet-4-5-20250929",
            goal="test goal",
            started_at="2024-01-01",
            completed_at="2024-01-01",
        ),
        summary="Test summary",
        turns=[
            {
                "turn": 1,
                "text": "Turn 1 text",
                "tool_calls": [{"name": "analyze_binary", "input": {}, "result": "result"}],
            }
        ],
        usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150, "api_calls": 1},
    )

    md_output = report.to_markdown()

    # Check for expected sections
    assert "# unfold Analysis Report" in md_output
    assert "**Binary:** test" in md_output
    assert "## Analysis" in md_output
    assert "## Summary" in md_output
    assert "Test summary" in md_output
    assert "## Analysis Log" in md_output
    assert "### Turn 1" in md_output
    assert "## Token Usage" in md_output


def test_report_to_html_produces_html():
    """Test Report.to_html() produces HTML with proper structure."""
    report = Report(
        version="0.2.0",
        binary=BinaryInfo(name="test", path="/test/binary"),
        analysis=AnalysisInfo(mode="explore", model="claude-sonnet-4-5-20250929"),
        summary="Test summary",
    )

    html_output = report.to_html()

    # Check for HTML structure
    assert "<!DOCTYPE html>" in html_output
    assert "<html" in html_output
    assert "<head>" in html_output
    assert "<body>" in html_output
    assert "<title>" in html_output
    assert "unfold Report" in html_output


def test_report_to_dict_has_all_required_keys():
    """Test Report.to_dict() has all required keys."""
    report = Report(
        version="0.2.0",
        binary=BinaryInfo(name="test", path="/test/binary", sha256="abc123", architecture="x86"),
        analysis=AnalysisInfo(
            mode="explore",
            model="claude-sonnet-4-5-20250929",
            goal="",
            started_at="2024-01-01",
            completed_at="2024-01-01",
        ),
        summary="Test summary",
        turns=[],
        usage={},
    )

    report_dict = report.to_dict()

    # Check all required keys
    assert "version" in report_dict
    assert "binary" in report_dict
    assert "analysis" in report_dict
    assert "summary" in report_dict
    assert "turns" in report_dict
    assert "usage" in report_dict

    # Check nested structure
    assert "name" in report_dict["binary"]
    assert "path" in report_dict["binary"]
    assert "sha256" in report_dict["binary"]
    assert "architecture" in report_dict["binary"]

    assert "mode" in report_dict["analysis"]
    assert "model" in report_dict["analysis"]
    assert "goal" in report_dict["analysis"]


def test_report_from_agent(tmp_binary, monkeypatch):
    """Test Report.from_agent() (mock agent)."""
    # Mock _ensure_ghidra_started
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)

    from pathlib import Path
    from unittest.mock import patch

    def mock_bridge_init(self, project_dir=None, ghidra_install_dir=None, java_home=None):
        self.project_dir = Path(project_dir or "/tmp/unfold_test_projects")
        self._project_names = {}

    monkeypatch.setattr("unfold.ghidra.bridge.GhidraBridge.__init__", mock_bridge_init)

    # Create a mock agent
    from unfold.agent.core import Agent
    from unfold.agent.usage import UsageTracker

    with patch("anthropic.Anthropic"):
        agent = Agent(binary_path=tmp_binary, mode="ctf")
        agent.turn_data = [
            {
                "turn": 1,
                "text": "Let me analyze...",
                "tool_calls": [
                    {
                        "name": "analyze_binary",
                        "input": {},
                        "result": json.dumps(
                            {"name": "test", "language": "x86:LE:64:default", "num_functions": 10}
                        ),
                    }
                ],
            }
        ]
        agent.usage = UsageTracker(model="claude-sonnet-4-5-20250929")
        agent.usage.input_tokens = 200
        agent.usage.output_tokens = 100

        report = Report.from_agent(agent, "Analysis complete.", goal="find the flag")

        assert report.binary.name == tmp_binary.name
        assert report.binary.path == str(tmp_binary.resolve())
        assert report.analysis.mode == "ctf"
        assert report.analysis.goal == "find the flag"
        assert report.summary == "Analysis complete."
        assert len(report.turns) == 1
        assert report.usage["input_tokens"] == 200
        assert report.usage["output_tokens"] == 100


def test_report_markdown_includes_goal_if_present():
    """Test Markdown report includes goal if present."""
    report = Report(
        analysis=AnalysisInfo(mode="ctf", model="claude-sonnet-4-5-20250929", goal="find the flag")
    )

    md_output = report.to_markdown()

    assert "**Goal:** find the flag" in md_output


def test_report_markdown_excludes_goal_if_empty():
    """Test Markdown report excludes goal if empty."""
    report = Report(
        analysis=AnalysisInfo(mode="explore", model="claude-sonnet-4-5-20250929", goal="")
    )

    md_output = report.to_markdown()

    assert "**Goal:**" not in md_output


def test_report_markdown_includes_tool_calls():
    """Test Markdown report includes tool call details."""
    report = Report(
        turns=[
            {
                "turn": 1,
                "text": "Analyzing...",
                "tool_calls": [
                    {
                        "name": "decompile",
                        "input": {"function": "main"},
                        "result": "int main() { return 0; }",
                    }
                ],
            }
        ]
    )

    md_output = report.to_markdown()

    assert "**Tool:** `decompile`" in md_output
    assert '"function": "main"' in md_output


def test_report_markdown_includes_usage_cost():
    """Test Markdown report includes estimated cost if present."""
    report = Report(
        usage={
            "input_tokens": 1000,
            "output_tokens": 500,
            "total_tokens": 1500,
            "api_calls": 2,
            "estimated_cost_usd": 0.0525,
        }
    )

    md_output = report.to_markdown()

    assert "**Estimated cost:** $0.0525" in md_output


def test_report_json_indentation():
    """Test Report.to_json() uses proper indentation."""
    report = Report(summary="Test")

    json_output = report.to_json()

    # Should be pretty-printed with indentation
    assert "\n" in json_output
    assert "  " in json_output  # Indentation


def test_report_to_dict_serialization():
    """Test Report.to_dict() serialization is complete."""
    report = Report(
        version="0.2.0",
        binary=BinaryInfo(name="test", path="/test/binary", sha256="abc", architecture="x86"),
        analysis=AnalysisInfo(
            mode="explore",
            model="claude-sonnet-4-5-20250929",
            goal="test",
            started_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T01:00:00",
        ),
        summary="Summary",
        turns=[{"turn": 1, "text": "Text", "tool_calls": []}],
        usage={"input_tokens": 100},
    )

    report_dict = report.to_dict()

    # Should be JSON-serializable
    json_str = json.dumps(report_dict)
    parsed = json.loads(json_str)

    assert parsed["version"] == "0.2.0"
    assert parsed["binary"]["name"] == "test"
    assert parsed["analysis"]["started_at"] == "2024-01-01T00:00:00"


def test_report_html_escapes_content():
    """Test HTML output escapes content properly."""
    report = Report(
        binary=BinaryInfo(name="<script>alert('xss')</script>", path="/test"),
        summary="Test <b>bold</b>",
    )

    html_output = report.to_html()

    # Should be escaped
    assert "&lt;script&gt;" in html_output or "alert" not in html_output
