"""Ghidra project management wrapper."""

from __future__ import annotations

from pathlib import Path

from .bridge import GhidraBridge


class GhidraProject:
    """Wrapper binding a GhidraBridge to a specific binary for a cleaner API."""

    def __init__(self, binary_path: Path | str, project_dir: Path | None = None):
        self.binary_path = Path(binary_path)
        self.bridge = GhidraBridge(project_dir=project_dir)

    def analyze(self) -> dict:
        return self.bridge.analyze(self.binary_path)

    def list_functions(self) -> list[dict]:
        return self.bridge.list_functions(self.binary_path)

    def decompile(self, function: str) -> dict:
        return self.bridge.decompile(self.binary_path, function)

    def get_xrefs_to(self, target: str) -> list[dict]:
        return self.bridge.get_xrefs_to(self.binary_path, target)

    def get_xrefs_from(self, target: str) -> list[dict]:
        return self.bridge.get_xrefs_from(self.binary_path, target)

    def get_strings(self) -> list[dict]:
        return self.bridge.get_strings(self.binary_path)

    def get_imports_exports(self) -> dict:
        return self.bridge.get_imports_exports(self.binary_path)

    def rename_function(self, target: str, new_name: str) -> dict:
        return self.bridge.rename_function(self.binary_path, target, new_name)

    def read_bytes(self, address: str, count: int) -> dict:
        return self.bridge.read_bytes(self.binary_path, address, count)
