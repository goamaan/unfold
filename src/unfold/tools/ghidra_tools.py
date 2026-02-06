"""Ghidra-backed tools for the agent."""

from __future__ import annotations

from typing import Callable

from unfold.ghidra.bridge import GhidraBridge


def get_ghidra_tools(bridge: GhidraBridge, binary_path) -> list[tuple[dict, Callable]]:
    """Return tool definitions and handlers for Ghidra operations."""

    tools = []

    # analyze_binary
    tools.append(
        (
            {
                "name": "analyze_binary",
                "description": "Import and run full analysis on the binary. Must be called before other tools. Returns basic binary info: architecture, format, function count.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            lambda **kwargs: bridge.analyze(binary_path),
        )
    )

    # list_functions
    tools.append(
        (
            {
                "name": "list_functions",
                "description": "List all functions in the binary with their names, addresses, and sizes. Use this to get an overview of the binary's structure.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            lambda **kwargs: bridge.list_functions(binary_path),
        )
    )

    # decompile
    tools.append(
        (
            {
                "name": "decompile",
                "description": "Decompile a specific function to C pseudocode. Provide either the function name (e.g. 'main', '_check_password') or its hex address (e.g. '0x100000460').",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "function": {
                            "type": "string",
                            "description": "Function name or hex address to decompile",
                        },
                    },
                    "required": ["function"],
                },
            },
            lambda function, **kwargs: bridge.decompile(binary_path, function),
        )
    )

    # get_xrefs_to
    tools.append(
        (
            {
                "name": "get_xrefs_to",
                "description": "Find all cross-references TO a function or address (i.e., who calls this function). Useful for understanding how a function is used.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Function name or hex address to find references to",
                        },
                    },
                    "required": ["target"],
                },
            },
            lambda target, **kwargs: bridge.get_xrefs_to(binary_path, target),
        )
    )

    # get_xrefs_from
    tools.append(
        (
            {
                "name": "get_xrefs_from",
                "description": "Find all cross-references FROM a function or address (i.e., what does this function call). Useful for understanding a function's dependencies.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Function name or hex address to find references from",
                        },
                    },
                    "required": ["target"],
                },
            },
            lambda target, **kwargs: bridge.get_xrefs_from(binary_path, target),
        )
    )

    # get_strings
    tools.append(
        (
            {
                "name": "get_strings",
                "description": "Extract all defined strings from the binary. Returns string values with their addresses. Useful for finding passwords, error messages, URLs, file paths, format strings, etc.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            lambda **kwargs: bridge.get_strings(binary_path),
        )
    )

    # get_imports_exports
    tools.append(
        (
            {
                "name": "get_imports_exports",
                "description": "List all imported library functions and exported symbols. Imported functions reveal what libraries/APIs the binary uses (e.g., crypto, network, file I/O). Exports show the binary's public API.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            lambda **kwargs: bridge.get_imports_exports(binary_path),
        )
    )

    # rename_function
    tools.append(
        (
            {
                "name": "rename_function",
                "description": "Rename a function to a more meaningful name. Use this to annotate the binary as you understand it. Provide the current name or address and the new name.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Current function name or hex address",
                        },
                        "new_name": {
                            "type": "string",
                            "description": "New descriptive name for the function",
                        },
                    },
                    "required": ["target", "new_name"],
                },
            },
            lambda target, new_name, **kwargs: bridge.rename_function(
                binary_path, target, new_name
            ),
        )
    )

    # read_bytes
    tools.append(
        (
            {
                "name": "read_bytes",
                "description": "Read raw bytes at a specific address. Returns hex dump and ASCII representation. Useful for examining data sections, encoded data, or raw instructions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "Hex address to read from (e.g. '0x100000460')",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of bytes to read (default: 64, max: 1024)",
                            "default": 64,
                        },
                    },
                    "required": ["address"],
                },
            },
            lambda address, count=64, **kwargs: bridge.read_bytes(
                binary_path, address, min(int(count), 1024)
            ),
        )
    )

    return tools
