"""Tests for GhidraBridge with mocks."""

from pathlib import Path

import pytest

from unfold.ghidra.bridge import GhidraBridge


@pytest.fixture
def mock_ghidra_startup(monkeypatch):
    """Mock _ensure_ghidra_started to avoid JVM initialization."""
    monkeypatch.setattr("unfold.ghidra.bridge._ensure_ghidra_started", lambda **kwargs: None)


def test_get_project_name_is_deterministic(mock_ghidra_startup, tmp_binary):
    """Test _get_project_name is deterministic."""
    bridge = GhidraBridge()

    name1 = bridge._get_project_name(tmp_binary)
    name2 = bridge._get_project_name(tmp_binary)

    assert name1 == name2


def test_get_project_name_caching(mock_ghidra_startup, tmp_binary):
    """Test _get_project_name caching works."""
    bridge = GhidraBridge()

    # First call
    name1 = bridge._get_project_name(tmp_binary)

    # Should be cached now
    assert str(tmp_binary.resolve()) in bridge._project_names

    # Second call should return cached value
    name2 = bridge._get_project_name(tmp_binary)

    assert name1 == name2


def test_project_name_format(mock_ghidra_startup, tmp_binary):
    """Test project name format is name_hash8."""
    bridge = GhidraBridge()

    project_name = bridge._get_project_name(tmp_binary)

    # Should be in format: stem_hash8
    assert "_" in project_name
    # Should start with the binary stem
    assert project_name.startswith(tmp_binary.stem)
    # Last 8 characters should be hex (the hash)
    hash_part = project_name[-8:]
    assert len(hash_part) == 8
    assert all(c in "0123456789abcdef" for c in hash_part)


def test_project_name_differs_for_different_paths(mock_ghidra_startup, tmp_path):
    """Test different binary paths produce different project names."""
    binary1 = tmp_path / "binary1"
    binary2 = tmp_path / "binary2"
    binary1.write_bytes(b"\x00" * 64)
    binary2.write_bytes(b"\x00" * 64)

    bridge = GhidraBridge()

    name1 = bridge._get_project_name(binary1)
    name2 = bridge._get_project_name(binary2)

    # Names should differ because paths differ
    assert name1 != name2


def test_bridge_init_sets_project_dir(mock_ghidra_startup, tmp_path):
    """Test GhidraBridge.__init__ sets project_dir correctly."""
    custom_dir = tmp_path / "custom_projects"
    bridge = GhidraBridge(project_dir=custom_dir)

    assert bridge.project_dir == custom_dir


def test_bridge_init_creates_project_dir(mock_ghidra_startup, tmp_path):
    """Test GhidraBridge.__init__ creates project_dir if it doesn't exist."""
    project_dir = tmp_path / "new_projects"
    assert not project_dir.exists()

    GhidraBridge(project_dir=project_dir)

    assert project_dir.exists()
    assert project_dir.is_dir()


def test_bridge_init_uses_default_project_dir(mock_ghidra_startup):
    """Test GhidraBridge uses default project_dir when not specified."""
    bridge = GhidraBridge()

    expected_default = Path.home() / ".unfold" / "projects"
    assert bridge.project_dir == expected_default


def test_bridge_init_initializes_project_names_cache(mock_ghidra_startup):
    """Test GhidraBridge initializes _project_names cache."""
    bridge = GhidraBridge()

    assert hasattr(bridge, "_project_names")
    assert isinstance(bridge._project_names, dict)
    assert len(bridge._project_names) == 0


def test_project_name_same_stem_different_paths(mock_ghidra_startup, tmp_path):
    """Test binaries with same name but different paths get different project names."""
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()

    binary1 = dir1 / "test"
    binary2 = dir2 / "test"
    binary1.write_bytes(b"\x00" * 64)
    binary2.write_bytes(b"\x00" * 64)

    bridge = GhidraBridge()

    name1 = bridge._get_project_name(binary1)
    name2 = bridge._get_project_name(binary2)

    # Both start with "test_" but have different hashes
    assert name1.startswith("test_")
    assert name2.startswith("test_")
    assert name1 != name2


def test_bridge_handles_relative_paths(mock_ghidra_startup, tmp_path):
    """Test bridge handles relative paths correctly."""
    binary = tmp_path / "test_binary"
    binary.write_bytes(b"\x00" * 64)

    bridge = GhidraBridge()

    # Get name with relative path
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        relative_path = Path("test_binary")
        name1 = bridge._get_project_name(relative_path)

        # Get name with absolute path
        name2 = bridge._get_project_name(binary)

        # Should be the same (both resolve to same absolute path)
        assert name1 == name2
    finally:
        os.chdir(original_cwd)


def test_ensure_ghidra_started_sets_global_flag():
    """Test _ensure_ghidra_started sets the global _ghidra_started flag."""
    import unfold.ghidra.bridge

    # Reset the flag
    original_flag = unfold.ghidra.bridge._ghidra_started
    unfold.ghidra.bridge._ghidra_started = False

    try:
        # Mock pyghidra module
        import sys
        from unittest.mock import MagicMock

        mock_pyghidra = MagicMock()
        mock_pyghidra.started.return_value = False
        mock_pyghidra.start = MagicMock()
        sys.modules["pyghidra"] = mock_pyghidra

        # Patch find_ghidra_install
        original_func = None
        try:
            import unfold.utils

            original_func = unfold.utils.find_ghidra_install
            unfold.utils.find_ghidra_install = lambda x: "/fake/ghidra"

            from unfold.ghidra.bridge import _ensure_ghidra_started

            _ensure_ghidra_started()

            assert unfold.ghidra.bridge._ghidra_started is True
        finally:
            if original_func:
                unfold.utils.find_ghidra_install = original_func
    finally:
        # Restore original state
        unfold.ghidra.bridge._ghidra_started = original_flag
        if "pyghidra" in sys.modules:
            del sys.modules["pyghidra"]


def test_ensure_ghidra_started_skips_if_already_started():
    """Test _ensure_ghidra_started skips initialization if already started."""
    import unfold.ghidra.bridge

    # Save original flag
    original_flag = unfold.ghidra.bridge._ghidra_started

    try:
        # Set flag to True
        unfold.ghidra.bridge._ghidra_started = True

        from unfold.ghidra.bridge import _ensure_ghidra_started

        # This should return immediately without importing pyghidra
        _ensure_ghidra_started()

        # If we get here without error, the test passes
        assert unfold.ghidra.bridge._ghidra_started is True
    finally:
        # Reset flag for other tests
        unfold.ghidra.bridge._ghidra_started = original_flag
