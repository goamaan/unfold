"""Utility functions for unfold."""

from __future__ import annotations

import logging
import os
from pathlib import Path


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Set up a logger with consistent formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def find_ghidra_install(ghidra_install_dir: str | None = None) -> Path | None:
    """Find the Ghidra installation path.

    Args:
        ghidra_install_dir: Explicit path from Config. Checked first.

    Checks in order:
    1. ghidra_install_dir argument (from Config)
    2. GHIDRA_INSTALL_DIR environment variable
    3. Common installation paths
    """
    # Config-provided path
    if ghidra_install_dir:
        path = Path(ghidra_install_dir).expanduser()
        if path.exists() and path.is_dir():
            return path

    # Environment variable
    env_path = os.getenv("GHIDRA_INSTALL_DIR")
    if env_path:
        path = Path(env_path)
        if path.exists() and path.is_dir():
            return path

    # Common installation paths
    common_paths = [
        "/opt/homebrew/Cellar/ghidra/*/libexec",
        "/usr/local/ghidra",
        "/opt/ghidra",
        "~/ghidra",
    ]

    for path_pattern in common_paths:
        expanded = Path(path_pattern).expanduser()

        if "*" in str(path_pattern):
            import glob

            matches = glob.glob(str(expanded))
            if matches:
                path = Path(sorted(matches)[-1])
                if path.exists() and path.is_dir():
                    return path
        else:
            if expanded.exists() and expanded.is_dir():
                return expanded

    return None
