"""Tests for rubric.py — load + version validation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from black_heron.rubric import load_rubric


def test_load_default_rubric_succeeds() -> None:
    """The bundled default rubric must load cleanly."""
    r = load_rubric(None)
    assert r.rubric_version
    assert r.schema_version == "1.0.0"
    assert r.cost_cap_usd > 0
    assert r.time_cap_seconds > 0


def test_default_rubric_has_severity_floors() -> None:
    r = load_rubric(None)
    assert "P0" in r.severity_confidence_floors
    assert r.severity_confidence_floors["P0"] >= 0.80  # P0 demands high confidence
    assert r.severity_confidence_floors["P1"] >= r.severity_confidence_floors["P2"]


def test_default_rubric_has_all_lenses_enabled() -> None:
    r = load_rubric(None)
    for lens in ("code_quality", "governance", "drift", "blind_spot"):
        assert lens in r.lens_enabled


def test_load_custom_rubric(tmp_path: Path) -> None:
    custom = tmp_path / "custom.json"
    custom.write_text(json.dumps({
        "rubric_version": "0.5.0",
        "schema_version": "1.0.0",
        "cost_cap_usd": 5.0,
        "time_cap_seconds": 600,
        "severity_confidence_floors": {"P0": 0.9, "P1": 0.75, "P2": 0.55},
        "severity_max_per_run": {"P0": 5, "P1": 15, "P2": 30},
        "kill_switch_total_findings_cap": 40,
        "lens_enabled": {"code_quality": True, "governance": True, "drift": False, "blind_spot": True},
    }))
    r = load_rubric(custom)
    assert r.rubric_version == "0.5.0"
    assert r.cost_cap_usd == 5.0
    assert r.lens_enabled["drift"] is False
    assert r.source == str(custom)


def test_load_rubric_rejects_unknown_schema_version(tmp_path: Path) -> None:
    bad = tmp_path / "future.json"
    bad.write_text(json.dumps({
        "rubric_version": "1.0.0",
        "schema_version": "2.0.0",  # not supported yet
    }))
    with pytest.raises(ValueError, match="schema_version"):
        load_rubric(bad)


def test_load_rubric_source_marks_bundled() -> None:
    r = load_rubric(None)
    assert r.source == "bundled-default"
