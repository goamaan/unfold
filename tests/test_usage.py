"""Tests for UsageTracker."""

from unittest.mock import MagicMock

import pytest

from unfold.agent.usage import UsageTracker


def test_initial_state_is_zero():
    """Test UsageTracker initial state is zero."""
    tracker = UsageTracker()

    assert tracker.input_tokens == 0
    assert tracker.output_tokens == 0
    assert tracker.api_calls == 0
    assert tracker.total_tokens == 0


def test_add_anthropic_accumulates():
    """Test add_anthropic accumulates token counts."""
    tracker = UsageTracker()

    # Create mock response
    response1 = MagicMock()
    response1.usage.input_tokens = 100
    response1.usage.output_tokens = 50

    response2 = MagicMock()
    response2.usage.input_tokens = 200
    response2.usage.output_tokens = 75

    tracker.add_anthropic(response1)
    tracker.add_anthropic(response2)

    assert tracker.input_tokens == 300
    assert tracker.output_tokens == 125
    assert tracker.api_calls == 2
    assert tracker.total_tokens == 425


def test_add_openai_accumulates():
    """Test add_openai accumulates token counts."""
    tracker = UsageTracker()

    # Create mock response
    response1 = MagicMock()
    response1.usage.prompt_tokens = 150
    response1.usage.completion_tokens = 60

    response2 = MagicMock()
    response2.usage.prompt_tokens = 250
    response2.usage.completion_tokens = 90

    tracker.add_openai(response1)
    tracker.add_openai(response2)

    assert tracker.input_tokens == 400
    assert tracker.output_tokens == 150
    assert tracker.api_calls == 2
    assert tracker.total_tokens == 550


def test_estimated_cost_usd_for_sonnet():
    """Test estimated_cost_usd for Sonnet model."""
    tracker = UsageTracker(model="claude-sonnet-4-5-20250929")
    tracker.input_tokens = 1_000_000  # 1M tokens
    tracker.output_tokens = 500_000  # 500K tokens

    # Sonnet pricing: $3 per 1M input, $15 per 1M output
    # Expected: (1M * 3 + 500K * 15) / 1M = 3 + 7.5 = 10.5
    cost = tracker.estimated_cost_usd

    assert cost == pytest.approx(10.5, rel=1e-6)


def test_estimated_cost_usd_for_opus():
    """Test estimated_cost_usd for Opus model."""
    tracker = UsageTracker(model="claude-opus-4-5-20250514")
    tracker.input_tokens = 1_000_000
    tracker.output_tokens = 500_000

    # Opus pricing: $15 per 1M input, $75 per 1M output
    # Expected: (1M * 15 + 500K * 75) / 1M = 15 + 37.5 = 52.5
    cost = tracker.estimated_cost_usd

    assert cost == pytest.approx(52.5, rel=1e-6)


def test_estimated_cost_usd_for_haiku():
    """Test estimated_cost_usd for Haiku model."""
    tracker = UsageTracker(model="claude-haiku-3-5-20241022")
    tracker.input_tokens = 1_000_000
    tracker.output_tokens = 500_000

    # Haiku pricing: $0.80 per 1M input, $4 per 1M output
    # Expected: (1M * 0.80 + 500K * 4) / 1M = 0.80 + 2.0 = 2.8
    cost = tracker.estimated_cost_usd

    assert cost == pytest.approx(2.8, rel=1e-6)


def test_estimated_cost_usd_for_unknown_model():
    """Test estimated_cost_usd returns 0 for unknown models."""
    tracker = UsageTracker(model="unknown-model")
    tracker.input_tokens = 1_000_000
    tracker.output_tokens = 500_000

    cost = tracker.estimated_cost_usd

    assert cost == 0.0


def test_summary_format():
    """Test summary() returns properly formatted string."""
    tracker = UsageTracker(model="claude-sonnet-4-5-20250929")
    tracker.input_tokens = 1500
    tracker.output_tokens = 800
    tracker.api_calls = 3

    summary = tracker.summary()

    assert "API calls: 3" in summary
    assert "Input tokens: 1,500" in summary
    assert "Output tokens: 800" in summary
    assert "Total tokens: 2,300" in summary
    assert "Estimated cost:" in summary


def test_summary_without_cost_for_unknown_model():
    """Test summary() doesn't include cost for unknown models."""
    tracker = UsageTracker(model="unknown-model")
    tracker.input_tokens = 1000
    tracker.output_tokens = 500
    tracker.api_calls = 1

    summary = tracker.summary()

    assert "API calls: 1" in summary
    assert "Input tokens: 1,000" in summary
    assert "Estimated cost:" not in summary


def test_to_dict_serialization():
    """Test to_dict() serialization."""
    tracker = UsageTracker(model="claude-sonnet-4-5-20250929")
    tracker.input_tokens = 2000
    tracker.output_tokens = 1000
    tracker.api_calls = 5

    result = tracker.to_dict()

    assert result["input_tokens"] == 2000
    assert result["output_tokens"] == 1000
    assert result["total_tokens"] == 3000
    assert result["api_calls"] == 5
    assert "estimated_cost_usd" in result
    assert isinstance(result["estimated_cost_usd"], float)


def test_to_dict_excludes_cost_for_unknown_model():
    """Test to_dict() excludes cost for unknown models."""
    tracker = UsageTracker(model="unknown-model")
    tracker.input_tokens = 1000
    tracker.output_tokens = 500
    tracker.api_calls = 2

    result = tracker.to_dict()

    assert result["input_tokens"] == 1000
    assert result["output_tokens"] == 500
    assert result["total_tokens"] == 1500
    assert result["api_calls"] == 2
    assert "estimated_cost_usd" not in result


def test_total_tokens_property():
    """Test total_tokens property calculates correctly."""
    tracker = UsageTracker()
    tracker.input_tokens = 300
    tracker.output_tokens = 200

    assert tracker.total_tokens == 500


def test_add_anthropic_with_missing_usage():
    """Test add_anthropic handles responses with missing usage."""
    tracker = UsageTracker()

    # Response with no usage attribute
    response = MagicMock()
    del response.usage

    tracker.add_anthropic(response)

    assert tracker.input_tokens == 0
    assert tracker.output_tokens == 0
    assert tracker.api_calls == 0


def test_add_openai_with_missing_usage():
    """Test add_openai handles responses with missing usage."""
    tracker = UsageTracker()

    # Response with no usage attribute
    response = MagicMock()
    del response.usage

    tracker.add_openai(response)

    assert tracker.input_tokens == 0
    assert tracker.output_tokens == 0
    assert tracker.api_calls == 0


def test_per_call_tracking():
    """Test that per-call tracking works."""
    tracker = UsageTracker()

    response1 = MagicMock()
    response1.usage.input_tokens = 100
    response1.usage.output_tokens = 50

    response2 = MagicMock()
    response2.usage.input_tokens = 200
    response2.usage.output_tokens = 75

    tracker.add_anthropic(response1)
    tracker.add_anthropic(response2)

    assert len(tracker._per_call) == 2
    assert tracker._per_call[0] == (100, 50)
    assert tracker._per_call[1] == (200, 75)


def test_cost_calculation_precision():
    """Test cost calculation handles small numbers precisely."""
    tracker = UsageTracker(model="claude-sonnet-4-5-20250929")
    tracker.input_tokens = 100
    tracker.output_tokens = 50

    # Sonnet: $3/1M input, $15/1M output
    # (100 * 3 + 50 * 15) / 1_000_000 = 1050 / 1_000_000 = 0.00105
    cost = tracker.estimated_cost_usd

    assert cost == pytest.approx(0.00105, rel=1e-6)


def test_summary_thousands_separator():
    """Test summary uses thousands separator for readability."""
    tracker = UsageTracker()
    tracker.input_tokens = 123456
    tracker.output_tokens = 789012
    tracker.api_calls = 42

    summary = tracker.summary()

    # Should have commas for thousands
    assert "123,456" in summary
    assert "789,012" in summary
    assert "912,468" in summary  # total


def test_to_dict_cost_rounding():
    """Test to_dict rounds cost to 6 decimal places."""
    tracker = UsageTracker(model="claude-sonnet-4-5-20250929")
    tracker.input_tokens = 123
    tracker.output_tokens = 456

    result = tracker.to_dict()

    cost = result["estimated_cost_usd"]
    # Should be rounded to 6 decimals
    assert isinstance(cost, float)
    # Convert to string to check decimal places
    cost_str = f"{cost:.6f}"
    assert len(cost_str.split(".")[-1]) == 6
