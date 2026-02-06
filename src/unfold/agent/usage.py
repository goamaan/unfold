"""Token usage tracking for LLM API calls."""

from __future__ import annotations

from dataclasses import dataclass, field

# Approximate pricing per 1M tokens (USD) — updated as needed
_PRICING: dict[str, tuple[float, float]] = {
    # (input_cost_per_1M, output_cost_per_1M)
    "claude-sonnet-4-5-20250929": (3.0, 15.0),
    "claude-opus-4-5-20250514": (15.0, 75.0),
    "claude-haiku-3-5-20241022": (0.80, 4.0),
}


@dataclass
class UsageTracker:
    """Accumulates token usage across API calls."""

    input_tokens: int = 0
    output_tokens: int = 0
    api_calls: int = 0
    model: str = ""
    _per_call: list[tuple[int, int]] = field(default_factory=list, repr=False)

    def add_anthropic(self, response) -> None:
        """Record usage from an Anthropic API response."""
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        inp = getattr(usage, "input_tokens", 0)
        out = getattr(usage, "output_tokens", 0)
        self.input_tokens += inp
        self.output_tokens += out
        self.api_calls += 1
        self._per_call.append((inp, out))

    def add_openai(self, response) -> None:
        """Record usage from an OpenAI-compatible API response."""
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        inp = getattr(usage, "prompt_tokens", 0)
        out = getattr(usage, "completion_tokens", 0)
        self.input_tokens += inp
        self.output_tokens += out
        self.api_calls += 1
        self._per_call.append((inp, out))

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """Estimate cost based on known model pricing."""
        pricing = _PRICING.get(self.model)
        if pricing is None:
            return 0.0
        input_cost, output_cost = pricing
        return (self.input_tokens * input_cost + self.output_tokens * output_cost) / 1_000_000

    def summary(self) -> str:
        """Return a formatted summary string."""
        lines = [
            f"API calls: {self.api_calls}",
            f"Input tokens: {self.input_tokens:,}",
            f"Output tokens: {self.output_tokens:,}",
            f"Total tokens: {self.total_tokens:,}",
        ]
        cost = self.estimated_cost_usd
        if cost > 0:
            lines.append(f"Estimated cost: ${cost:.4f}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, int | float]:
        """Serialize for report/session export."""
        result: dict[str, int | float] = {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "api_calls": self.api_calls,
        }
        cost = self.estimated_cost_usd
        if cost > 0:
            result["estimated_cost_usd"] = round(cost, 6)
        return result
