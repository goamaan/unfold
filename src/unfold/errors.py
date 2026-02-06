"""Exception hierarchy for unfold."""

from __future__ import annotations


class UnfoldError(Exception):
    """Base exception for unfold."""


class ConfigError(UnfoldError):
    """Configuration-related errors (missing file, invalid values)."""


class GhidraError(UnfoldError):
    """Ghidra/PyGhidra operation failures."""


class APIError(UnfoldError):
    """LLM API call failures (auth, rate limit, timeout)."""
