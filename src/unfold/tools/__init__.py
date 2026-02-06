"""Tool registry for the unfold agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from unfold.ghidra.bridge import GhidraBridge


def get_all_tools(
    bridge: GhidraBridge, binary_path: Path
) -> tuple[list[dict], dict[str, Callable]]:
    """Collect all tools and return them in Claude API format.

    Returns:
        A tuple of (tool_definitions, handler_map).
    """
    from .file_tools import get_file_tools
    from .ghidra_tools import get_ghidra_tools

    all_tool_pairs = []
    all_tool_pairs.extend(get_ghidra_tools(bridge, binary_path))
    all_tool_pairs.extend(get_file_tools(binary_path))

    tool_definitions = []
    handler_map = {}

    for tool_def, handler in all_tool_pairs:
        tool_definitions.append(tool_def)
        handler_map[tool_def["name"]] = handler

    return tool_definitions, handler_map


def execute_tool(handler_map: dict[str, Callable], tool_name: str, tool_input: dict) -> str:
    """Execute a tool and return the result as a JSON string."""
    # Some proxies prepend prefixes to tool names — strip common ones
    resolved_name = tool_name
    if resolved_name not in handler_map:
        for prefix in ("proxy_", "functions.", "tools."):
            stripped = resolved_name.removeprefix(prefix)
            if stripped in handler_map:
                resolved_name = stripped
                break

    if resolved_name not in handler_map:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = handler_map[resolved_name](**tool_input)
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2)
        return str(result)
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)

        # Provide better messages for common JVM/Ghidra issues
        if "jpype" in error_type.lower() or "jvm" in error_msg.lower():
            error_msg = (
                f"JVM error during {tool_name}: {error_msg}. "
                "If this is an OutOfMemoryError, try: export _JAVA_OPTIONS='-Xmx4g'"
            )
        elif "NullPointerException" in error_msg:
            error_msg = (
                f"Ghidra returned null during {tool_name}. "
                "The binary may not have been analyzed yet — try analyze_binary first."
            )

        return json.dumps({"error": f"{error_type}: {error_msg}"})
