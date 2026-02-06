"""Session persistence — save and resume analysis conversations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from unfold.agent.core import Agent

SESSIONS_DIR = Path.home() / ".unfold" / "sessions"


def save_session(agent: Agent) -> Path:
    """Save the current agent state to a session file.

    Returns:
        Path to the saved session file.
    """
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{agent.binary_path.stem}_{timestamp}.json"
    session_path = SESSIONS_DIR / filename

    # Serialize messages — convert non-serializable content blocks
    serialized_messages = []
    for msg in agent.messages:
        serialized_messages.append(_serialize_message(msg))

    session_data = {
        "version": "0.2.0",
        "binary_path": str(agent.binary_path),
        "mode": agent.mode,
        "model": agent.model,
        "max_turns": agent.max_turns,
        "stream": agent.stream,
        "messages": serialized_messages,
        "turn_data": agent.turn_data,
        "usage": agent.usage.to_dict(),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }

    session_path.write_text(json.dumps(session_data, indent=2, default=str))

    # Also create/update a "latest" symlink
    latest_path = SESSIONS_DIR / "latest.json"
    try:
        if latest_path.exists() or latest_path.is_symlink():
            latest_path.unlink()
        latest_path.symlink_to(session_path)
    except OSError:
        pass

    return session_path


def load_session(session_path: str | Path) -> dict:
    """Load a session file and return the session data dict."""
    path = Path(session_path)
    if not path.exists():
        raise FileNotFoundError(f"Session file not found: {path}")

    data: dict = json.loads(path.read_text())

    # Validate
    if "binary_path" not in data or "messages" not in data:
        raise ValueError(f"Invalid session file: {path}")

    return data


def list_sessions(console: Console) -> None:
    """Print a table of saved sessions."""
    from rich.table import Table

    if not SESSIONS_DIR.exists():
        console.print("[dim]No saved sessions found.[/dim]")
        return

    session_files = sorted(SESSIONS_DIR.glob("*.json"), reverse=True)
    # Exclude the "latest.json" symlink from listing
    session_files = [f for f in session_files if f.name != "latest.json"]

    if not session_files:
        console.print("[dim]No saved sessions found.[/dim]")
        return

    table = Table(title="Saved Sessions")
    table.add_column("File", style="cyan")
    table.add_column("Binary", style="bold")
    table.add_column("Mode")
    table.add_column("Model")
    table.add_column("Turns", justify="right")
    table.add_column("Saved At")

    for sf in session_files[:20]:  # Show max 20
        try:
            data = json.loads(sf.read_text())
            binary_name = Path(data.get("binary_path", "?")).name
            mode = data.get("mode", "?")
            model = data.get("model", "?")
            turns = len(data.get("turn_data", []))
            saved_at = data.get("saved_at", "?")
            if saved_at != "?":
                # Shorten ISO format
                saved_at = saved_at[:19].replace("T", " ")
            table.add_row(sf.name, binary_name, mode, model, str(turns), saved_at)
        except Exception:
            table.add_row(sf.name, "?", "?", "?", "?", "?")

    console.print(table)


def _serialize_message(msg: dict) -> dict:
    """Serialize a message dict, converting Anthropic content blocks to dicts."""
    role = msg.get("role", "")
    content = msg.get("content", "")

    if isinstance(content, str):
        return {"role": role, "content": content}

    if isinstance(content, list):
        serialized_content: list[dict] = []
        for item in content:
            if isinstance(item, dict):
                serialized_content.append(item)
            elif hasattr(item, "type"):
                # Anthropic content block object
                block_dict: dict = {"type": item.type}
                if item.type == "text":
                    block_dict["text"] = item.text
                elif item.type == "tool_use":
                    block_dict["id"] = item.id
                    block_dict["name"] = item.name
                    block_dict["input"] = item.input
                elif item.type == "tool_result":
                    block_dict["tool_use_id"] = getattr(item, "tool_use_id", "")
                    block_dict["content"] = getattr(item, "content", "")
                serialized_content.append(block_dict)
            else:
                serialized_content.append({"type": "unknown", "value": str(item)})
        return {"role": role, "content": serialized_content}

    return {"role": role, "content": str(content)}
