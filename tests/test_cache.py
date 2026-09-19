"""Tests for content-hash cache (Phase S, v1.3.2)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from black_heron._models import EntryPoint, Finding, RepoContext
from black_heron.cache import (
    CACHE_FORMAT_VERSION,
    CacheStats,
    compute_cache_key,
    compute_ctx_hash,
    compute_findings_hash,
    deserialize_cached_findings,
    purge_cache,
    read_cache,
    run_lens_with_cache,
    write_cache,
)


def _make_ctx(
    *,
    file_listing=None,
    sample_files=None,
    entry_points=None,
    todo_count=0,
) -> RepoContext:
    return RepoContext(
        path="/tmp/repo",
        file_count=len(file_listing) if file_listing else 0,
        primary_language="python",
        file_listing=file_listing or ["a.py", "b.py"],
        sample_files=sample_files or {"a.py": "x = 1"},
        entry_points=entry_points or [],
        git_log_recent=[],
        todo_count=todo_count,
    )


def _make_finding(
    *,
    lens="code_quality",
    file="src/x.py",
    lines="L42",
    severity="P1",
    claim="Some issue with the code",
    evidence="x = 1",
) -> Finding:
    return Finding(
        lens=lens,
        severity=severity,
        file=file,
        lines=lines,
        claim=claim,
        evidence=evidence,
        why_it_matters="matters",
        confidence=0.8,
    )


# ----- ctx hash -----


def test_ctx_hash_stable_across_calls():
    ctx1 = _make_ctx()
    ctx2 = _make_ctx()
    assert compute_ctx_hash(ctx1) == compute_ctx_hash(ctx2)


def test_ctx_hash_changes_on_sample_file_content():
    ctx1 = _make_ctx(sample_files={"a.py": "x = 1"})
    ctx2 = _make_ctx(sample_files={"a.py": "x = 2"})
    assert compute_ctx_hash(ctx1) != compute_ctx_hash(ctx2)


def test_ctx_hash_changes_on_entry_point():
    ctx1 = _make_ctx(entry_points=[
        EntryPoint(path="main.py", role="cli_entry", content="print(1)")
    ])
    ctx2 = _make_ctx(entry_points=[
        EntryPoint(path="main.py", role="cli_entry", content="print(2)")
    ])
    assert compute_ctx_hash(ctx1) != compute_ctx_hash(ctx2)


def test_ctx_hash_changes_on_todo_count():
    ctx1 = _make_ctx(todo_count=0)
    ctx2 = _make_ctx(todo_count=5)
    assert compute_ctx_hash(ctx1) != compute_ctx_hash(ctx2)


# ----- cache key -----


def test_cache_key_includes_lens_name():
    h = "a" * 64
    k1 = compute_cache_key(h, "code_quality", "claude-opus-4-6", "1.0.0")
    k2 = compute_cache_key(h, "governance", "claude-opus-4-6", "1.0.0")
    assert k1 != k2


def test_cache_key_includes_model():
    h = "a" * 64
    k1 = compute_cache_key(h, "code_quality", "claude-opus-4-6", "1.0.0")
    k2 = compute_cache_key(h, "code_quality", "claude-opus-4-7", "1.0.0")
    assert k1 != k2


def test_cache_key_includes_rubric_version():
    h = "a" * 64
    k1 = compute_cache_key(h, "code_quality", "claude-opus-4-6", "1.0.0")
    k2 = compute_cache_key(h, "code_quality", "claude-opus-4-6", "2.0.0")
    assert k1 != k2


def test_cache_key_includes_prior_findings_hash():
    h = "a" * 64
    k1 = compute_cache_key(h, "blind_spot", "claude-opus-4-6", "1.0.0", "")
    k2 = compute_cache_key(h, "blind_spot", "claude-opus-4-6", "1.0.0", "p1")
    assert k1 != k2


# ----- findings hash -----


def test_findings_hash_stable_with_reordering():
    f1 = _make_finding(lens="code_quality", file="src/a.py")
    f2 = _make_finding(lens="governance", file="src/b.py")
    h1 = compute_findings_hash([f1, f2])
    h2 = compute_findings_hash([f2, f1])
    assert h1 == h2, "findings_hash should be order-insensitive"


def test_findings_hash_changes_on_new_finding():
    f1 = _make_finding(file="src/a.py", claim="A")
    f2 = _make_finding(file="src/b.py", claim="B")
    h1 = compute_findings_hash([f1])
    h2 = compute_findings_hash([f1, f2])
    assert h1 != h2


def test_findings_hash_empty_list():
    h = compute_findings_hash([])
    assert isinstance(h, str)
    assert len(h) == 64


# ----- write/read round-trip -----


def test_write_then_read_roundtrip(tmp_path: Path):
    key = "a" * 64
    findings = [_make_finding(claim="abc"), _make_finding(claim="def")]
    write_cache(tmp_path, key, "code_quality", findings)
    cached = read_cache(tmp_path, key, "code_quality")
    assert cached is not None
    assert len(cached) == 2
    assert cached[0]["claim"] == "abc"
    assert cached[1]["claim"] == "def"


def test_read_miss_returns_none(tmp_path: Path):
    assert read_cache(tmp_path, "missingkey", "code_quality") is None


def test_corrupted_json_returns_none(tmp_path: Path):
    key = "b" * 64
    cache_file = tmp_path / key[:2] / key[2:18] / "code_quality.json"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("{not json", encoding="utf-8")
    assert read_cache(tmp_path, key, "code_quality") is None


def test_format_version_mismatch_returns_none(tmp_path: Path):
    key = "c" * 64
    cache_file = tmp_path / key[:2] / key[2:18] / "code_quality.json"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text(
        json.dumps({"format_version": "0", "findings": []}), encoding="utf-8"
    )
    assert read_cache(tmp_path, key, "code_quality") is None


def test_findings_field_not_list_returns_none(tmp_path: Path):
    key = "d" * 64
    cache_file = tmp_path / key[:2] / key[2:18] / "code_quality.json"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text(
        json.dumps({"format_version": CACHE_FORMAT_VERSION, "findings": "oops"}),
        encoding="utf-8",
    )
    assert read_cache(tmp_path, key, "code_quality") is None


# ----- deserialize -----


def test_deserialize_skips_invalid_findings():
    valid = _make_finding(claim="ok").model_dump()
    invalid = {"lens": "x", "severity": "BOGUS", "file": "f", "lines": "L1"}
    out = deserialize_cached_findings([valid, invalid])
    assert len(out) == 1
    assert out[0].claim == "ok"


# ----- run_lens_with_cache (miss then hit) -----


def test_run_lens_with_cache_miss_then_hit(tmp_path: Path):
    calls = {"count": 0}

    def lens_call():
        calls["count"] += 1
        return [_make_finding(claim="first call")]

    stats = CacheStats(cache_dir=str(tmp_path), enabled=True)
    common_kwargs = dict(
        lens_name="code_quality",
        lens_model="claude-opus-4-6",
        ctx_hash="x" * 64,
        rubric_version="1.0.0",
        cache_dir=tmp_path,
        cache_stats=stats,
        enabled=True,
    )

    # Miss
    out1 = run_lens_with_cache(**common_kwargs, lens_call=lens_call)
    assert len(out1) == 1
    assert calls["count"] == 1
    assert stats.misses == 1
    assert stats.hits == 0

    # Hit (lens_call should NOT be invoked)
    out2 = run_lens_with_cache(**common_kwargs, lens_call=lens_call)
    assert len(out2) == 1
    assert calls["count"] == 1, "second call should hit cache, not invoke lens"
    assert stats.hits == 1
    assert stats.misses == 1


def test_run_lens_with_cache_bypass_when_disabled(tmp_path: Path):
    calls = {"count": 0}

    def lens_call():
        calls["count"] += 1
        return [_make_finding()]

    stats = CacheStats(cache_dir=str(tmp_path), enabled=False)

    for _ in range(3):
        run_lens_with_cache(
            lens_name="code_quality",
            lens_model="claude-opus-4-6",
            ctx_hash="x" * 64,
            rubric_version="1.0.0",
            cache_dir=tmp_path,
            cache_stats=stats,
            enabled=False,
            lens_call=lens_call,
        )

    assert calls["count"] == 3
    assert stats.bypassed == 3
    assert stats.hits == 0
    assert stats.misses == 0


def test_run_lens_with_cache_write_failure_does_not_abort(tmp_path: Path):
    """If write_cache raises OSError, the audit must continue with the live result."""

    def lens_call():
        return [_make_finding(claim="ok")]

    stats = CacheStats(cache_dir=str(tmp_path), enabled=True)

    with patch("black_heron.cache.write_cache", side_effect=OSError("disk full")):
        out = run_lens_with_cache(
            lens_name="code_quality",
            lens_model="claude-opus-4-6",
            ctx_hash="y" * 64,
            rubric_version="1.0.0",
            cache_dir=tmp_path,
            cache_stats=stats,
            enabled=True,
            lens_call=lens_call,
        )

    assert len(out) == 1
    assert out[0].claim == "ok"
    assert stats.misses == 1


# ----- purge -----


def test_purge_cache_removes_files(tmp_path: Path):
    key = "e" * 64
    write_cache(tmp_path, key, "code_quality", [_make_finding()])
    write_cache(tmp_path, key, "governance", [_make_finding()])

    count = purge_cache(tmp_path)
    assert count >= 2
    assert read_cache(tmp_path, key, "code_quality") is None
    assert read_cache(tmp_path, key, "governance") is None


def test_purge_cache_on_missing_dir():
    nonexistent = Path("/tmp/never-existed-bh-cache-xyzzy-12345")
    if nonexistent.exists():
        return  # skip; real path exists
    assert purge_cache(nonexistent) == 0
