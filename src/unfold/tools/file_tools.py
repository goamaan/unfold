"""File and binary analysis tools using standard Unix utilities."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Callable


def get_file_tools(binary_path: Path) -> list[tuple[dict, Callable]]:
    """Return tool definitions and handlers for file-based analysis."""
    binary_path = Path(binary_path)
    tools = []

    def file_info_handler(**kwargs) -> str:
        try:
            result = subprocess.run(
                ["file", str(binary_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error: {e}"

    tools.append(
        (
            {
                "name": "file_info",
                "description": "Get file type and format information using the 'file' command. Quick way to identify architecture, format (ELF/Mach-O/PE), and whether it's stripped.",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            file_info_handler,
        )
    )

    def binary_info_handler(**kwargs) -> str:
        parts = []
        # Try otool (macOS)
        try:
            r = subprocess.run(
                ["otool", "-h", str(binary_path)], capture_output=True, text=True, timeout=10
            )
            parts.append("=== Mach-O Header ===\n" + r.stdout.strip())
            r = subprocess.run(
                ["otool", "-L", str(binary_path)], capture_output=True, text=True, timeout=10
            )
            parts.append("\n=== Shared Libraries ===\n" + r.stdout.strip())
            return "\n".join(parts)
        except FileNotFoundError:
            pass
        # Try readelf (Linux)
        try:
            r = subprocess.run(
                ["readelf", "-h", str(binary_path)], capture_output=True, text=True, timeout=10
            )
            return "=== ELF Header ===\n" + r.stdout.strip()
        except FileNotFoundError:
            return "Error: Neither otool nor readelf found"

    tools.append(
        (
            {
                "name": "binary_info",
                "description": "Get binary header info and shared library dependencies using otool (macOS) or readelf (Linux).",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            binary_info_handler,
        )
    )

    def raw_strings_handler(min_length: int = 4, **kwargs) -> str:
        try:
            result = subprocess.run(
                ["strings", "-n", str(min_length), str(binary_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout
        except Exception as e:
            return f"Error: {e}"

    tools.append(
        (
            {
                "name": "raw_strings",
                "description": "Extract printable strings from the binary using the Unix 'strings' command. Faster than Ghidra's string analysis but less precise.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "min_length": {
                            "type": "integer",
                            "description": "Minimum string length (default: 4)",
                            "default": 4,
                        },
                    },
                    "required": [],
                },
            },
            raw_strings_handler,
        )
    )

    def binary_size_handler(**kwargs) -> dict:
        try:
            size = binary_path.stat().st_size
            md5 = hashlib.md5()
            sha256 = hashlib.sha256()
            with open(binary_path, "rb") as f:
                while chunk := f.read(8192):
                    md5.update(chunk)
                    sha256.update(chunk)
            return {
                "file_size": size,
                "file_size_human": _format_size(size),
                "md5": md5.hexdigest(),
                "sha256": sha256.hexdigest(),
            }
        except Exception as e:
            return {"error": str(e)}

    tools.append(
        (
            {
                "name": "binary_size",
                "description": "Get file size and cryptographic hashes (MD5, SHA256) of the binary.",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            binary_size_handler,
        )
    )

    return tools


def _format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"
