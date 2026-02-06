"""Tests for tool registry and execution."""

import json

from unfold.tools import execute_tool, get_all_tools


def test_get_all_tools_returns_correct_count(mock_bridge, tmp_binary):
    """Test get_all_tools returns correct number of tools (9 ghidra + 4 file = 13)."""
    tool_defs, handler_map = get_all_tools(mock_bridge, tmp_binary)

    assert len(tool_defs) == 13
    assert len(handler_map) == 13


def test_tool_definitions_have_required_keys(mock_bridge, tmp_binary):
    """Test all tool definitions have required keys."""
    tool_defs, _ = get_all_tools(mock_bridge, tmp_binary)

    for tool_def in tool_defs:
        assert "name" in tool_def
        assert "description" in tool_def
        assert "input_schema" in tool_def
        assert isinstance(tool_def["name"], str)
        assert isinstance(tool_def["description"], str)
        assert isinstance(tool_def["input_schema"], dict)


def test_ghidra_tool_names(mock_bridge, tmp_binary):
    """Test that all expected Ghidra tools are present."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    expected_ghidra_tools = [
        "analyze_binary",
        "list_functions",
        "decompile",
        "get_xrefs_to",
        "get_xrefs_from",
        "get_strings",
        "get_imports_exports",
        "rename_function",
        "read_bytes",
    ]

    for tool_name in expected_ghidra_tools:
        assert tool_name in handler_map


def test_file_tool_names(mock_bridge, tmp_binary):
    """Test that all expected file tools are present."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    expected_file_tools = [
        "file_info",
        "binary_info",
        "raw_strings",
        "binary_size",
    ]

    for tool_name in expected_file_tools:
        assert tool_name in handler_map


def test_execute_tool_with_valid_tool(mock_bridge, tmp_binary):
    """Test execute_tool with a valid tool name."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    # Test with a simple tool (binary_size)
    result = execute_tool(handler_map, "binary_size", {})

    # Result should be JSON-parseable
    parsed = json.loads(result)
    assert "file_size" in parsed
    assert "sha256" in parsed


def test_execute_tool_with_unknown_tool(mock_bridge, tmp_binary):
    """Test execute_tool with unknown tool returns error JSON."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    result = execute_tool(handler_map, "unknown_tool", {})

    parsed = json.loads(result)
    assert "error" in parsed
    assert "Unknown tool: unknown_tool" in parsed["error"]


def test_prefix_stripping_proxy(mock_bridge, tmp_binary):
    """Test that proxy_ prefix is stripped correctly."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    # Add a handler without prefix
    handler_map["analyze_binary"] = lambda **kwargs: {"success": True}

    # Try calling with proxy_ prefix
    result = execute_tool(handler_map, "proxy_analyze_binary", {})

    parsed = json.loads(result)
    assert parsed == {"success": True}


def test_prefix_stripping_functions(mock_bridge, tmp_binary):
    """Test that functions. prefix is stripped correctly."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    handler_map["decompile"] = lambda **kwargs: {"success": True}

    result = execute_tool(handler_map, "functions.decompile", {"function": "main"})

    parsed = json.loads(result)
    assert parsed == {"success": True}


def test_prefix_stripping_tools(mock_bridge, tmp_binary):
    """Test that tools. prefix is stripped correctly."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    handler_map["get_strings"] = lambda **kwargs: {"success": True}

    result = execute_tool(handler_map, "tools.get_strings", {})

    parsed = json.loads(result)
    assert parsed == {"success": True}


def test_tool_handler_error_handling(mock_bridge, tmp_binary):
    """Test that errors in tool handlers are caught and returned as JSON."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    # Replace a handler with one that raises an exception
    def failing_handler(**kwargs):
        raise ValueError("Test error message")

    handler_map["analyze_binary"] = failing_handler

    result = execute_tool(handler_map, "analyze_binary", {})

    parsed = json.loads(result)
    assert "error" in parsed
    assert "ValueError" in parsed["error"]
    assert "Test error message" in parsed["error"]


def test_tool_returns_dict_as_json(mock_bridge, tmp_binary):
    """Test that tools returning dicts are serialized as JSON."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    handler_map["test_tool"] = lambda **kwargs: {"key": "value", "number": 42}

    result = execute_tool(handler_map, "test_tool", {})

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert parsed == {"key": "value", "number": 42}


def test_tool_returns_list_as_json(mock_bridge, tmp_binary):
    """Test that tools returning lists are serialized as JSON."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    handler_map["test_tool"] = lambda **kwargs: [{"item": 1}, {"item": 2}]

    result = execute_tool(handler_map, "test_tool", {})

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert parsed == [{"item": 1}, {"item": 2}]


def test_tool_returns_string_as_is(mock_bridge, tmp_binary):
    """Test that tools returning plain strings return them as-is."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    handler_map["test_tool"] = lambda **kwargs: "plain string result"

    result = execute_tool(handler_map, "test_tool", {})

    assert result == "plain string result"


def test_jvm_error_message_enhancement(mock_bridge, tmp_binary):
    """Test that JVM errors get enhanced error messages."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    def jvm_failing_handler(**kwargs):
        raise RuntimeError("JVM OutOfMemoryError occurred")

    handler_map["analyze_binary"] = jvm_failing_handler

    result = execute_tool(handler_map, "analyze_binary", {})

    parsed = json.loads(result)
    assert "error" in parsed
    assert "JVM" in parsed["error"]
    assert "_JAVA_OPTIONS" in parsed["error"]


def test_null_pointer_error_message_enhancement(mock_bridge, tmp_binary):
    """Test that NullPointerException errors get enhanced messages."""
    _, handler_map = get_all_tools(mock_bridge, tmp_binary)

    def null_failing_handler(**kwargs):
        raise RuntimeError("java.lang.NullPointerException at line 42")

    handler_map["decompile"] = null_failing_handler

    result = execute_tool(handler_map, "decompile", {"function": "main"})

    parsed = json.loads(result)
    assert "error" in parsed
    assert "Ghidra returned null" in parsed["error"]
    assert "analyze_binary" in parsed["error"]
