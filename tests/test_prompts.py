"""Tests for the prompt system."""

import pytest

from unfold.agent.prompts import MODES, SYSTEM_BASE, get_system_prompt


def test_all_modes_return_valid_prompts():
    """Test all 5 modes return valid prompts."""
    modes = ["explore", "ctf", "vuln", "annotate", "explain"]

    for mode in modes:
        prompt = get_system_prompt(mode)
        assert isinstance(prompt, str)
        assert len(prompt) > 0


def test_unknown_mode_raises_value_error():
    """Test unknown mode raises ValueError."""
    with pytest.raises(ValueError, match="Unknown mode: invalid_mode"):
        get_system_prompt("invalid_mode")


def test_system_base_included_in_all_modes():
    """Test SYSTEM_BASE is included in all mode prompts."""
    modes = ["explore", "ctf", "vuln", "annotate", "explain"]

    for mode in modes:
        prompt = get_system_prompt(mode)
        # Check that key phrases from SYSTEM_BASE are present
        assert "reverse engineer" in prompt.lower()
        assert "ghidra" in prompt.lower()
        assert "analyze_binary" in prompt


def test_explore_mode_contains_keywords():
    """Test explore mode contains mode-specific keywords."""
    prompt = get_system_prompt("explore")

    assert "explore" in prompt.lower() or "exploration" in prompt.lower()
    assert "comprehensive" in prompt.lower() or "systematically" in prompt.lower()
    assert "what does this program do" in prompt.lower()


def test_ctf_mode_contains_keywords():
    """Test CTF mode contains mode-specific keywords."""
    prompt = get_system_prompt("ctf")

    assert "ctf" in prompt.lower()
    assert "flag" in prompt.lower()
    assert "challenge" in prompt.lower()


def test_vuln_mode_contains_keywords():
    """Test vulnerability mode contains mode-specific keywords."""
    prompt = get_system_prompt("vuln")

    assert "vulnerability" in prompt.lower() or "vulnerabilities" in prompt.lower()
    assert "buffer overflow" in prompt.lower()
    assert "security" in prompt.lower() or "exploit" in prompt.lower()


def test_annotate_mode_contains_keywords():
    """Test annotate mode contains mode-specific keywords."""
    prompt = get_system_prompt("annotate")

    assert "annotate" in prompt.lower() or "annotation" in prompt.lower()
    assert "rename" in prompt.lower()
    assert "meaningful names" in prompt.lower() or "descriptive name" in prompt.lower()


def test_explain_mode_contains_keywords():
    """Test explain mode contains mode-specific keywords."""
    prompt = get_system_prompt("explain")

    assert "explain" in prompt.lower() or "explanation" in prompt.lower()
    assert "what is this program" in prompt.lower() or "what does this binary" in prompt.lower()
    assert "documentation" in prompt.lower() or "high-level" in prompt.lower()


def test_modes_dict_has_all_expected_keys():
    """Test MODES dict has all expected mode keys."""
    expected_modes = ["explore", "ctf", "vuln", "annotate", "explain"]

    for mode in expected_modes:
        assert mode in MODES


def test_prompts_contain_tool_recommendations():
    """Test that prompts contain recommendations for tool usage."""
    prompt = get_system_prompt("explore")

    # Should mention key tools
    assert "analyze_binary" in prompt
    assert "list_functions" in prompt
    assert "decompile" in prompt


def test_prompts_are_unique_per_mode():
    """Test that each mode has unique content."""
    modes = ["explore", "ctf", "vuln", "annotate", "explain"]
    prompts = {mode: get_system_prompt(mode) for mode in modes}

    # Check that prompts are different
    prompt_values = list(prompts.values())
    unique_prompts = set(prompt_values)
    assert len(unique_prompts) == len(modes), "All mode prompts should be unique"


def test_system_base_structure():
    """Test SYSTEM_BASE has expected structure."""
    assert "expert reverse engineer" in SYSTEM_BASE.lower()
    assert "ghidra" in SYSTEM_BASE.lower()
    assert isinstance(SYSTEM_BASE, str)
    assert len(SYSTEM_BASE) > 100


def test_vuln_mode_lists_vulnerability_types():
    """Test vulnerability mode lists specific vulnerability types."""
    prompt = get_system_prompt("vuln")

    vuln_types = [
        "buffer overflow",
        "format string",
        "integer overflow",
        "use-after-free",
        "double-free",
    ]

    for vuln_type in vuln_types:
        assert vuln_type in prompt.lower()


def test_ctf_mode_mentions_flag_formats():
    """Test CTF mode mentions common flag formats."""
    prompt = get_system_prompt("ctf")

    # Should mention flag formats or validation
    assert "flag{" in prompt.lower() or "ctf{" in prompt.lower() or "picoctf{" in prompt.lower()
