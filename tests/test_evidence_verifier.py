"""Tests for evidence_verifier.py — substring presence check."""
from __future__ import annotations

from black_heron._models import EntryPoint, Finding, RepoContext
from black_heron.evidence_verifier import _norm, check_evidence_in_context


def _make_ctx(samples: dict[str, str], entry_points: list[tuple[str, str]] | None = None) -> RepoContext:
    return RepoContext(
        path="/tmp/test",
        file_count=len(samples),
        primary_language="Python",
        file_listing=list(samples.keys()),
        sample_files=samples,
        entry_points=[
            EntryPoint(path=p, role="module_init", content=c, truncated=False)
            for p, c in (entry_points or [])
        ],
        git_log_recent=[],
        todo_count=0,
    )


def _make_finding(evidence: str) -> Finding:
    return Finding(
        lens="code_quality",
        severity="P1",
        file="example.py",
        lines="L1",
        claim="Test claim",
        evidence=evidence,
        why_it_matters="Test rationale",
        confidence=0.8,
    )


def test_evidence_found_in_sample() -> None:
    ctx = _make_ctx({"example.py": "def hello():\n    return 'world hello universe'\n"})
    f = _make_finding("return 'world hello universe'")
    result = check_evidence_in_context([f], ctx)
    assert result[0] is True


def test_evidence_not_in_bundle() -> None:
    ctx = _make_ctx({"example.py": "actually different content here all together"})
    f = _make_finding("this string does not appear anywhere in the bundle ever")
    result = check_evidence_in_context([f], ctx)
    assert result[0] is False


def test_evidence_too_short_passes_through() -> None:
    # Evidence < 20 chars skips substring check (too noisy)
    ctx = _make_ctx({"example.py": "completely different content not related"})
    f = _make_finding("short")
    result = check_evidence_in_context([f], ctx)
    assert result[0] is True  # passes through


def test_evidence_in_entry_point_content() -> None:
    ctx = _make_ctx(
        samples={},
        entry_points=[("pyproject.toml", "name = \"my-pkg-test-12345\"\nversion = \"1.0.0\"")],
    )
    f = _make_finding("name = \"my-pkg-test-12345\"")
    result = check_evidence_in_context([f], ctx)
    assert result[0] is True


def test_evidence_normalization_whitespace_collapse() -> None:
    # Multiple internal whitespace runs should collapse to single space
    # for both the haystack and the needle, allowing the match to land.
    ctx = _make_ctx({"example.py": "actually   contains\nthe  required\tstring here"})
    f = _make_finding("actually contains the required string here")
    result = check_evidence_in_context([f], ctx)
    assert result[0] is True


def test_norm_collapses_whitespace_and_lowercases() -> None:
    assert _norm("  Hello\n\tWorld  ") == "hello world"
    assert _norm("ALL CAPS HERE") == "all caps here"


def test_empty_evidence_passes() -> None:
    ctx = _make_ctx({"x.py": "content"})
    f = Finding(
        lens="code_quality",
        severity="P2",
        file="x.py",
        lines="L1",
        claim="",
        evidence="",
        why_it_matters="",
        confidence=0.5,
    )
    result = check_evidence_in_context([f], ctx)
    assert result[0] is True  # empty evidence → let verifier handle
