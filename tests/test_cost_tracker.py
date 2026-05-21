"""Tests for cost_tracker.py — price math, cap enforcement."""
from __future__ import annotations

from black_heron.cost_tracker import PRICES, CostTracker, DEFAULT_PRICE


def test_known_models_in_price_table() -> None:
    assert "claude-opus-4-6" in PRICES
    assert "claude-opus-4-7" in PRICES
    assert "claude-sonnet-4-6" in PRICES


def test_opus_pricing_higher_than_sonnet() -> None:
    assert PRICES["claude-opus-4-6"]["input"] > PRICES["claude-sonnet-4-6"]["input"]
    assert PRICES["claude-opus-4-6"]["output"] > PRICES["claude-sonnet-4-6"]["output"]


def test_default_price_is_conservative_opus_tier() -> None:
    # Falling back to most-expensive tier ensures we don't under-bill silently
    assert DEFAULT_PRICE["input"] >= 15.0
    assert DEFAULT_PRICE["output"] >= 75.0


def test_tracker_zero_state() -> None:
    t = CostTracker(cost_cap_usd=2.0)
    assert t.cost_so_far == 0.0
    assert t.exceeded() is False
    assert t.lens_cost == {}


def test_tracker_records_cost() -> None:
    t = CostTracker(cost_cap_usd=2.0)
    # 1M input + 1M output Opus 4.6 = $15 + $75 = $90
    cost = t.record(
        model="claude-opus-4-6",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert cost == 90.0
    assert t.cost_so_far == 90.0
    # Cap is $2, so we're way over
    assert t.exceeded() is True


def test_tracker_records_per_lens() -> None:
    t = CostTracker(cost_cap_usd=10.0)
    t.record(
        model="claude-opus-4-6",
        input_tokens=10_000,
        output_tokens=5_000,
        lens_name="code_quality",
    )
    t.record(
        model="claude-opus-4-6",
        input_tokens=8_000,
        output_tokens=4_000,
        lens_name="governance",
    )
    assert "code_quality" in t.lens_cost
    assert "governance" in t.lens_cost
    assert t.cost_so_far == sum(t.lens_cost.values())


def test_tracker_unknown_model_uses_default() -> None:
    t = CostTracker(cost_cap_usd=10.0)
    cost = t.record(
        model="claude-unknown-future-9-9",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    # Default price input is opus-tier ($15/M)
    assert cost == 15.0


def test_tracker_cache_tokens_billed_correctly() -> None:
    t = CostTracker(cost_cap_usd=10.0)
    cost = t.record(
        model="claude-opus-4-6",
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=1_000_000,  # opus cache read = $1.50/M
    )
    assert abs(cost - 1.50) < 0.001


def test_tracker_exceeded_only_above_cap() -> None:
    t = CostTracker(cost_cap_usd=5.0)
    t.cost_so_far = 4.99
    assert t.exceeded() is False
    t.cost_so_far = 5.00
    assert t.exceeded() is True
    t.cost_so_far = 5.01
    assert t.exceeded() is True
