"""Utility functions for unfold."""

import logging
import os
from pathlib import Path
from typing import Optional

# Configure logging
def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Set up a logger with consistent formatting.

    Args:
        name: Logger name
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding multiple handlers if logger already exists
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def find_ghidra_install() -> Optional[Path]:
    """Find the Ghidra installation path.

    Checks in the following order:
    1. GHIDRA_INSTALL_DIR environment variable
    2. Common installation paths (e.g., /opt/homebrew/Cellar/ghidra/*/libexec)

    Returns:
        Path to Ghidra installation directory, or None if not found
    """
    # Check environment variable first
    env_path = os.getenv('GHIDRA_INSTALL_DIR')
    if env_path:
        path = Path(env_path)
        if path.exists() and path.is_dir():
            return path

    # Check common installation paths
    common_paths = [
        '/opt/homebrew/Cellar/ghidra/*/libexec',
        '/usr/local/ghidra',
        '/opt/ghidra',
        '~/ghidra',
    ]

    for path_pattern in common_paths:
        expanded = Path(path_pattern).expanduser()

        # Handle glob patterns
        if '*' in str(path_pattern):
            import glob
            matches = glob.glob(str(expanded))
            if matches:
                # Return the first (or newest) match
                path = Path(sorted(matches)[-1])
                if path.exists() and path.is_dir():
                    return path
        else:
            if expanded.exists() and expanded.is_dir():
                return expanded

    return None
