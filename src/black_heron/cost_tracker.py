"""Cost tracker — accumulates API spend, kill-switches when cap exceeded."""
from __future__ import annotations

from dataclasses import dataclass, field

# Token costs in USD per 1M tokens (snapshot 2026-05; verify before re-pricing)
# Conservative, slightly high — better to over-estimate cost than under.
PRICES = {
    "claude-opus-4-6": {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    "claude-opus-4-7": {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
}

DEFAULT_PRICE = {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75}


@dataclass
class CostTracker:
    cost_cap_usd: float = 2.0
    cost_so_far: float = 0.0
    lens_cost: dict[str, float] = field(default_factory=dict)

    def record(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
        lens_name: str | None = None,
    ) -> float:
        price = PRICES.get(model, DEFAULT_PRICE)
        cost = (
            (input_tokens / 1_000_000) * price["input"]
            + (output_tokens / 1_000_000) * price["output"]
            + (cache_read_tokens / 1_000_000) * price["cache_read"]
            + (cache_creation_tokens / 1_000_000) * price["cache_write"]
        )
        self.cost_so_far += cost
        if lens_name is not None:
            self.lens_cost[lens_name] = self.lens_cost.get(lens_name, 0.0) + cost
        return cost

    def exceeded(self) -> bool:
        return self.cost_so_far >= self.cost_cap_usd


def record_response(
    tracker: CostTracker,
    response,
    *,
    model: str,
    lens_name: str | None = None,
) -> float:
    """Extract usage from an Anthropic SDK response and record it."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0.0
    return tracker.record(
        model=model,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        lens_name=lens_name,
    )
