"""Tests for the deterministic baseline-drift module.

Phase R is set arithmetic on identity hashes; no LLM, no API. Every bucket
assignment is verified against the identity heuristic + drift triggers
documented in src/black_heron/drift.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from black_heron.drift import (
    categorize,
    compute_drift_from_file,
    compute_identity_hash,
    load_baseline_findings,
)


def _f(**kwargs) -> dict:
    """Build a finding dict with sensible defaults."""
    base = {
        "lens": "code_quality",
        "severity": "P1",
        "file": "src/x.py",
        "lines": "L10-L20",
        "claim": "Function does not validate input length",
        "evidence": "if user_input:",
        "why_it_matters": "boundary check missing",
        "confidence": 0.8,
    }
    base.update(kwargs)
    return base


# ---------- identity hash --------------------------------------------------


def test_identity_hash_stable_across_line_format_variants() -> None:
    a = _f(lines="L42-L88")
    b = _f(lines="L42")
    c = _f(lines="42-88")
    h = compute_identity_hash(a)
    assert compute_identity_hash(b) == h
    assert compute_identity_hash(c) == h


def test_identity_hash_robust_to_claim_rephrasing() -> None:
    # First 8 words match exactly; only the trailing words differ -> same hash
    a = _f(claim="The auth middleware does not validate token expiration before granting access to admin")
    b = _f(claim="The auth middleware does not validate token expiration on every request as documented")
    assert compute_identity_hash(a) == compute_identity_hash(b)


def test_identity_hash_robust_to_punctuation_and_case() -> None:
    a = _f(claim="The auth middleware does not validate token expiration.")
    b = _f(claim="THE AUTH MIDDLEWARE does NOT validate token expiration!")
    assert compute_identity_hash(a) == compute_identity_hash(b)


def test_identity_hash_changes_when_file_differs() -> None:
    a = _f(file="src/a.py")
    b = _f(file="src/b.py")
    assert compute_identity_hash(a) != compute_identity_hash(b)


def test_identity_hash_changes_when_lens_differs() -> None:
    a = _f(lens="code_quality")
    b = _f(lens="governance")
    assert compute_identity_hash(a) != compute_identity_hash(b)


def test_identity_hash_changes_when_claim_prefix_differs() -> None:
    a = _f(claim="Function does not validate input length")
    b = _f(claim="Module does not validate input length")
    assert compute_identity_hash(a) != compute_identity_hash(b)


def test_identity_hash_handles_missing_fields() -> None:
    # No exceptions, deterministic hash from empty parts
    h = compute_identity_hash({})
    assert isinstance(h, str) and len(h) == 64


# ---------- categorize ------------------------------------------------------


def test_categorize_empty_baseline_all_new() -> None:
    current = [_f(), _f(file="src/y.py")]
    report = categorize(current, [])
    assert report.available is True
    assert len(report.new) == 2
    assert report.closed == []
    assert report.persisting == []
    assert report.drifted == []


def test_categorize_identical_current_baseline_all_persisting() -> None:
    findings = [_f(), _f(file="src/y.py", claim="Other issue different words entirely now")]
    report = categorize(findings, findings)
    assert len(report.persisting) == 2
    assert report.new == []
    assert report.closed == []
    assert report.drifted == []


def test_categorize_closed_bucket() -> None:
    base = [_f(), _f(file="src/y.py")]
    cur = [_f(file="src/y.py")]
    report = categorize(cur, base)
    assert len(report.closed) == 1
    assert report.closed[0]["file"] == "src/x.py"
    assert len(report.persisting) == 1


def test_categorize_drifted_on_severity_change() -> None:
    base = [_f(severity="P2", confidence=0.65)]
    cur = [_f(severity="P1", confidence=0.65)]
    report = categorize(cur, base)
    assert report.persisting == []
    assert len(report.drifted) == 1
    reasons = report.drifted[0]["drift_reasons"]
    assert any("severity:P2->P1" in r for r in reasons)


def test_categorize_drifted_on_confidence_jump() -> None:
    base = [_f(confidence=0.50)]
    cur = [_f(confidence=0.85)]
    report = categorize(cur, base)
    assert len(report.drifted) == 1
    assert any("confidence" in r for r in report.drifted[0]["drift_reasons"])


def test_categorize_persisting_on_tiny_confidence_drift() -> None:
    # 0.15 delta is below threshold -> persisting, not drifted
    base = [_f(confidence=0.70)]
    cur = [_f(confidence=0.85)]
    report = categorize(cur, base)
    assert len(report.persisting) == 1
    assert report.drifted == []


def test_categorize_drifted_on_evidence_change() -> None:
    base = [_f(evidence="if user_input:")]
    cur = [_f(evidence="if entirely_different_branch:")]
    report = categorize(cur, base)
    assert len(report.drifted) == 1
    assert "evidence:changed" in report.drifted[0]["drift_reasons"]


def test_categorize_persisting_when_evidence_is_superstring() -> None:
    # broaden quote without changing the underlying issue
    base = [_f(evidence="if user_input:")]
    cur = [_f(evidence="    if user_input:\n        return None")]
    report = categorize(cur, base)
    assert len(report.persisting) == 1
    assert report.drifted == []


def test_categorize_attaches_identity_hash_to_outputs() -> None:
    cur = [_f()]
    report = categorize(cur, [])
    assert "identity_hash" in report.new[0]
    assert len(report.new[0]["identity_hash"]) == 64


# ---------- baseline loader -------------------------------------------------


def test_load_baseline_handles_missing_path(tmp_path: Path) -> None:
    report = compute_drift_from_file([_f()], tmp_path / "does_not_exist.json")
    assert report.available is False
    assert "does not exist" in (report.skipped_reason or "")
    # audit-side fields zeroed
    assert report.new == [] and report.closed == [] and report.persisting == [] and report.drifted == []


def test_load_baseline_handles_none_path() -> None:
    report = compute_drift_from_file([_f()], None)
    assert report.available is False
    assert report.skipped_reason == "no --baseline path supplied"


def test_load_baseline_handles_malformed_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    report = compute_drift_from_file([_f()], bad)
    assert report.available is False
    assert "malformed" in (report.skipped_reason or "")


def test_load_baseline_handles_unrecognized_shape(tmp_path: Path) -> None:
    weird = tmp_path / "weird.json"
    weird.write_text(json.dumps({"random_key": [1, 2, 3]}), encoding="utf-8")
    report = compute_drift_from_file([_f()], weird)
    assert report.available is False
    assert "no recognizable findings array" in (report.skipped_reason or "")


def test_load_baseline_accepts_full_findings_json_shape(tmp_path: Path) -> None:
    payload = {
        "schema_version": "1.0.0",
        "generated_at_utc": "2026-05-21T00:00:00+00:00",
        "verified": [_f()],
        "rejected": [],
    }
    p = tmp_path / "findings.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    findings, generated, err = load_baseline_findings(p)
    assert err is None
    assert len(findings) == 1
    assert generated == "2026-05-21T00:00:00+00:00"


def test_load_baseline_accepts_bare_list(tmp_path: Path) -> None:
    p = tmp_path / "bare.json"
    p.write_text(json.dumps([_f(), _f(file="src/y.py")]), encoding="utf-8")
    findings, generated, err = load_baseline_findings(p)
    assert err is None
    assert len(findings) == 2


def test_load_baseline_accepts_generic_findings_key(tmp_path: Path) -> None:
    p = tmp_path / "g.json"
    p.write_text(json.dumps({"findings": [_f()]}), encoding="utf-8")
    findings, _generated, err = load_baseline_findings(p)
    assert err is None and len(findings) == 1


# ---------- payload shape ---------------------------------------------------


def test_to_payload_contains_all_buckets_and_counts() -> None:
    base = [_f(), _f(file="src/y.py")]
    cur = [_f(), _f(file="src/z.py")]
    report = categorize(cur, base)
    p = report.to_payload()
    assert p["available"] is True
    assert set(p["counts"]) == {"new", "closed", "persisting", "drifted"}
    assert p["counts"]["new"] == 1
    assert p["counts"]["closed"] == 1
    assert p["counts"]["persisting"] == 1
    assert p["counts"]["drifted"] == 0
