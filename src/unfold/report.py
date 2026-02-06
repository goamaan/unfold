"""Report generation for unfold analysis results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from unfold.agent.core import Agent


@dataclass
class BinaryInfo:
    """Metadata about the analyzed binary."""

    name: str = ""
    path: str = ""
    sha256: str = ""
    architecture: str = ""


@dataclass
class AnalysisInfo:
    """Metadata about the analysis run."""

    mode: str = ""
    model: str = ""
    goal: str = ""
    started_at: str = ""
    completed_at: str = ""


@dataclass
class Report:
    """Complete analysis report."""

    version: str = "0.2.0"
    binary: BinaryInfo = field(default_factory=BinaryInfo)
    analysis: AnalysisInfo = field(default_factory=AnalysisInfo)
    summary: str = ""
    turns: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)

    @classmethod
    def from_agent(cls, agent: Agent, summary: str, goal: str | None = None) -> Report:
        """Build a report from a completed Agent run."""
        import hashlib

        # Compute binary sha256
        sha256 = ""
        try:
            h = hashlib.sha256()
            with open(agent.binary_path, "rb") as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            sha256 = h.hexdigest()
        except Exception:
            pass

        # Try to get architecture from turn data
        architecture = ""
        for turn in agent.turn_data:
            for tc in turn.get("tool_calls", []):
                if tc.get("name") == "analyze_binary":
                    try:
                        result_data = json.loads(tc.get("result", "{}"))
                        architecture = result_data.get("language", "")
                    except (json.JSONDecodeError, TypeError):
                        pass

        now = datetime.now(timezone.utc).isoformat()

        return cls(
            binary=BinaryInfo(
                name=agent.binary_path.name,
                path=str(agent.binary_path),
                sha256=sha256,
                architecture=architecture,
            ),
            analysis=AnalysisInfo(
                mode=agent.mode,
                model=agent.model,
                goal=goal or "",
                started_at=now,
                completed_at=now,
            ),
            summary=summary,
            turns=list(agent.turn_data),
            usage=agent.usage.to_dict(),
        )

    def to_dict(self) -> dict:
        """Serialize to a dict."""
        return {
            "version": self.version,
            "binary": {
                "name": self.binary.name,
                "path": self.binary.path,
                "sha256": self.binary.sha256,
                "architecture": self.binary.architecture,
            },
            "analysis": {
                "mode": self.analysis.mode,
                "model": self.analysis.model,
                "goal": self.analysis.goal,
                "started_at": self.analysis.started_at,
                "completed_at": self.analysis.completed_at,
            },
            "summary": self.summary,
            "turns": self.turns,
            "usage": self.usage,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Generate a Markdown report."""
        lines = []
        lines.append("# unfold Analysis Report\n")
        lines.append(f"**Binary:** {self.binary.name}  ")
        lines.append(f"**Path:** `{self.binary.path}`  ")
        if self.binary.sha256:
            lines.append(f"**SHA256:** `{self.binary.sha256}`  ")
        if self.binary.architecture:
            lines.append(f"**Architecture:** {self.binary.architecture}  ")
        lines.append("")

        lines.append("## Analysis\n")
        lines.append(f"- **Mode:** {self.analysis.mode}")
        lines.append(f"- **Model:** {self.analysis.model}")
        if self.analysis.goal:
            lines.append(f"- **Goal:** {self.analysis.goal}")
        lines.append(f"- **Completed:** {self.analysis.completed_at}")
        lines.append("")

        lines.append("## Summary\n")
        lines.append(self.summary)
        lines.append("")

        if self.turns:
            lines.append("## Analysis Log\n")
            for turn in self.turns:
                lines.append(f"### Turn {turn.get('turn', '?')}\n")
                text = turn.get("text", "")
                if text:
                    lines.append(text)
                    lines.append("")
                for tc in turn.get("tool_calls", []):
                    name = tc.get("name", "?")
                    inp = tc.get("input", {})
                    result_preview = tc.get("result", "")[:300]
                    lines.append(f"**Tool:** `{name}`")
                    if inp:
                        lines.append(f"```json\n{json.dumps(inp, indent=2)}\n```")
                    if result_preview:
                        lines.append("<details><summary>Result</summary>\n")
                        lines.append(f"```\n{result_preview}\n```\n")
                        lines.append("</details>\n")
                lines.append("")

        if self.usage:
            lines.append("## Token Usage\n")
            lines.append(f"- **Input tokens:** {self.usage.get('input_tokens', 0):,}")
            lines.append(f"- **Output tokens:** {self.usage.get('output_tokens', 0):,}")
            lines.append(f"- **Total tokens:** {self.usage.get('total_tokens', 0):,}")
            lines.append(f"- **API calls:** {self.usage.get('api_calls', 0)}")
            cost = self.usage.get("estimated_cost_usd")
            if cost:
                lines.append(f"- **Estimated cost:** ${cost:.4f}")
            lines.append("")

        lines.append("---\n")
        lines.append("*Generated by [unfold](https://github.com/goamaan/unfold) v0.2.0*\n")

        return "\n".join(lines)

    def to_html(self) -> str:
        """Generate a standalone HTML report."""
        md = self.to_markdown()

        # Simple markdown-to-HTML conversion for standalone reports
        import html as html_module

        escaped = html_module.escape(md)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>unfold Report - {html_module.escape(self.binary.name)}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
            background: #0d1117;
            color: #c9d1d9;
            line-height: 1.6;
        }}
        h1, h2, h3 {{ color: #58a6ff; }}
        code, pre {{
            background: #161b22;
            padding: 0.2em 0.4em;
            border-radius: 6px;
            font-size: 0.9em;
        }}
        pre {{
            padding: 1em;
            overflow-x: auto;
            border: 1px solid #30363d;
        }}
        details {{
            background: #161b22;
            padding: 0.5em 1em;
            border-radius: 6px;
            margin: 0.5em 0;
            border: 1px solid #30363d;
        }}
        summary {{ cursor: pointer; color: #58a6ff; }}
        hr {{ border-color: #30363d; }}
        a {{ color: #58a6ff; }}
    </style>
</head>
<body>
<pre style="white-space: pre-wrap; font-family: inherit; background: none; border: none; padding: 0;">
{escaped}
</pre>
</body>
</html>"""
