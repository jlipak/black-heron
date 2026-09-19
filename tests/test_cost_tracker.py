"""Tests for cost_tracker.py — price math, cap enforcement."""
from __future__ import annotations

from black_heron.cost_tracker import DEFAULT_PRICE, PRICES, CostTracker


def test_known_models_in_price_table() -> None:
    assert "claude-opus-5" in PRICES
    assert "claude-opus-4-8" in PRICES
    assert "claude-sonnet-5" in PRICES


def test_opus_pricing_higher_than_sonnet() -> None:
    assert PRICES["claude-opus-5"]["input"] > PRICES["claude-sonnet-5"]["input"]
    assert PRICES["claude-opus-5"]["output"] > PRICES["claude-sonnet-5"]["output"]


def test_default_price_is_at_least_the_dearest_known_tier() -> None:
    # Falling back to the most expensive tier ensures we don't under-bill silently
    assert DEFAULT_PRICE["input"] >= max(p["input"] for p in PRICES.values())
    assert DEFAULT_PRICE["output"] >= max(p["output"] for p in PRICES.values())


def test_cache_prices_follow_the_documented_multipliers() -> None:
    # cache read = 0.1x input, cache write (5-minute TTL) = 1.25x input
    for model, price in PRICES.items():
        assert abs(price["cache_read"] - 0.1 * price["input"]) < 1e-9, model
        assert abs(price["cache_write"] - 1.25 * price["input"]) < 1e-9, model


def test_tracker_zero_state() -> None:
    t = CostTracker(cost_cap_usd=2.0)
    assert t.cost_so_far == 0.0
    assert t.exceeded() is False
    assert t.lens_cost == {}


def test_tracker_records_cost() -> None:
    t = CostTracker(cost_cap_usd=2.0)
    # 1M input + 1M output on Opus 5 = $5 + $25 = $30
    cost = t.record(
        model="claude-opus-5",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert cost == 30.0
    assert t.cost_so_far == 30.0
    # Cap is $2, so we're way over
    assert t.exceeded() is True


def test_tracker_records_per_lens() -> None:
    t = CostTracker(cost_cap_usd=10.0)
    t.record(
        model="claude-opus-4-8",
        input_tokens=10_000,
        output_tokens=5_000,
        lens_name="code_quality",
    )
    t.record(
        model="claude-opus-4-8",
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
    assert cost == DEFAULT_PRICE["input"]


def test_tracker_cache_tokens_billed_correctly() -> None:
    t = CostTracker(cost_cap_usd=10.0)
    cost = t.record(
        model="claude-opus-5",
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=1_000_000,  # Opus 5 cache read = $0.50/M
    )
    assert abs(cost - 0.50) < 0.001


def test_tracker_exceeded_only_above_cap() -> None:
    t = CostTracker(cost_cap_usd=5.0)
    t.cost_so_far = 4.99
    assert t.exceeded() is False
    t.cost_so_far = 5.00
    assert t.exceeded() is True
    t.cost_so_far = 5.01
    assert t.exceeded() is True
