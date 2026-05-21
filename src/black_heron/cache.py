"""Content-hash cache for lens outputs.

When `ctx` (repo content) + lens metadata are unchanged across runs, the
Anthropic API call is skipped and the prior lens output is replayed from
`~/.black-heron/cache/`.

Discipline notes:
- Cache is observable, deterministic (Law VII). No LLM is consulted.
- Cache key embeds rubric_version + lens model id, so any meaningful upstream
  change forces a fresh API call (Law V — never claim cached when source moved).
- Corrupted cache entries are skipped, not raised (Law IV — partial result over
  crash).
- Writes are atomic via `.tmp` + os.replace.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ._models import Finding, RepoContext

DEFAULT_CACHE_DIR = Path.home() / ".black-heron" / "cache"

# Bump when on-disk cache schema changes. Forces re-population on upgrade
# (never silent invalidation — old entries remain readable but new format wins
# because the key changes).
CACHE_FORMAT_VERSION = "1"


def compute_ctx_hash(ctx: RepoContext) -> str:
    """Deterministic SHA256 of RepoContext content.

    Captures: file_listing, sample_files contents, entry_points contents, git
    log, todo_count, external_enrichments. Two ctx objects with identical
    repo state produce the same hash regardless of dict insertion order.
    """
    payload = ctx.model_dump(mode="json")
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def compute_findings_hash(findings: list) -> str:
    """Hash a list of findings (used as part of blind_spot cache key).

    Sort by (file, lines, claim_prefix) so order-jitter from concurrent first-
    pass lenses doesn't invalidate the cache. Each finding contributes only its
    identity-bearing fields, not noisy metadata.
    """
    items: list[tuple[str, str, str, str, str]] = []
    for f in findings:
        d = f.model_dump() if hasattr(f, "model_dump") else dict(f)
        claim = (d.get("claim") or "").strip().lower()[:80]
        items.append((
            d.get("lens", ""),
            d.get("file", ""),
            d.get("lines", ""),
            d.get("severity", ""),
            claim,
        ))
    items.sort()
    canon = json.dumps(items, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def compute_cache_key(
    ctx_hash: str,
    lens_name: str,
    lens_model: str,
    rubric_version: str,
    prior_findings_hash: str = "",
) -> str:
    """Combine inputs into a stable per-(lens, run-config) cache key."""
    parts = [
        CACHE_FORMAT_VERSION,
        ctx_hash,
        lens_name,
        lens_model,
        rubric_version,
        prior_findings_hash,
    ]
    key_str = "|".join(parts)
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()


@dataclass
class CacheStats:
    """Per-run cache outcome counters. Surfaced in REPORT.md + findings.json."""

    hits: int = 0
    misses: int = 0
    bypassed: int = 0
    cache_dir: str = ""
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "hits": self.hits,
            "misses": self.misses,
            "bypassed": self.bypassed,
            "cache_dir": self.cache_dir,
        }


def _cache_file_path(cache_dir: Path, cache_key: str, lens_name: str) -> Path:
    # Shard by first 2 hex chars to keep directory listings manageable
    return cache_dir / cache_key[:2] / cache_key[2:18] / f"{lens_name}.json"


def read_cache(
    cache_dir: Path,
    cache_key: str,
    lens_name: str,
) -> Optional[list[dict]]:
    """Read cached lens output.

    Returns the list of finding dicts on hit, None on miss / corruption /
    missing. Corruption is logged to stderr and treated as miss (Law IV —
    silent failure forbidden, but partial degradation is acceptable).
    """
    cache_file = _cache_file_path(cache_dir, cache_key, lens_name)
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.stderr.write(
            f"[bh:cache] corrupt cache file (treating as miss): "
            f"{cache_file.name}: {e}\n"
        )
        return None
    if not isinstance(data, dict):
        return None
    if data.get("format_version") != CACHE_FORMAT_VERSION:
        # Old schema — treat as miss; on re-write we overwrite with new format
        return None
    findings = data.get("findings")
    if not isinstance(findings, list):
        return None
    return findings


def write_cache(
    cache_dir: Path,
    cache_key: str,
    lens_name: str,
    findings: list,
    metadata: dict | None = None,
) -> None:
    """Atomic write of lens output to cache.

    `findings` may be either list[Finding] or list[dict]. Pydantic models are
    serialized via model_dump.
    """
    cache_file = _cache_file_path(cache_dir, cache_key, lens_name)
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    serialized: list[dict] = []
    for f in findings:
        if hasattr(f, "model_dump"):
            serialized.append(f.model_dump())
        elif isinstance(f, dict):
            serialized.append(f)
        # silently drop anything else — never break a good run on a stray type

    payload = {
        "format_version": CACHE_FORMAT_VERSION,
        "cache_key": cache_key,
        "lens_name": lens_name,
        "findings": serialized,
        "written_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if metadata:
        payload["metadata"] = metadata

    tmp = cache_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(cache_file))


def deserialize_cached_findings(cached: list[dict]) -> list[Finding]:
    """Re-hydrate cached finding dicts into Pydantic Finding objects.

    Validation errors are skipped with a stderr note (one bad entry shouldn't
    block the rest). This mirrors the parse_findings tolerance in lenses/_common.
    """
    out: list[Finding] = []
    for d in cached:
        try:
            out.append(Finding(**d))
        except Exception as e:
            sys.stderr.write(
                f"[bh:cache] skip invalid cached finding: "
                f"{type(e).__name__}: {str(e)[:120]}\n"
            )
            continue
    return out


def run_lens_with_cache(
    *,
    lens_name: str,
    lens_model: str,
    ctx_hash: str,
    rubric_version: str,
    cache_dir: Path,
    cache_stats: CacheStats,
    enabled: bool,
    lens_call,  # callable taking no args, returns list[Finding]
    prior_findings_hash: str = "",
) -> list[Finding]:
    """Wrap a lens call with cache lookup.

    `lens_call` is a zero-arg closure that performs the actual API call when
    a miss is detected. Decoupling via closure handles the heterogeneous lens
    signatures (blind_spot vs first-pass) without refactoring lens modules.

    Counter updates touch `cache_stats` in place. ThreadPoolExecutor workers
    can call this concurrently — GIL makes int += atomic enough for the small
    counters we keep.
    """
    if not enabled:
        cache_stats.bypassed += 1
        return lens_call()

    key = compute_cache_key(
        ctx_hash, lens_name, lens_model, rubric_version, prior_findings_hash
    )
    cached = read_cache(cache_dir, key, lens_name)
    if cached is not None:
        cache_stats.hits += 1
        return deserialize_cached_findings(cached)

    cache_stats.misses += 1
    findings = lens_call()
    try:
        write_cache(cache_dir, key, lens_name, findings)
    except OSError as e:
        # Bad disk, full disk, permissions — never abort a successful audit
        # because the cache layer failed downstream of the actual work.
        sys.stderr.write(f"[bh:cache] write skipped ({lens_name}): {e}\n")
    return findings


def purge_cache(cache_dir: Path) -> int:
    """Delete all cached entries. Returns count of files removed.

    Exposed so a user can wipe the cache explicitly when they suspect drift
    (e.g., after upgrading the rubric or a lens prompt outside the version
    bump path).
    """
    if not cache_dir.exists():
        return 0
    count = 0
    for f in cache_dir.rglob("*.json"):
        try:
            f.unlink()
            count += 1
        except OSError:
            pass
    # Clean empty leaf dirs bottom-up
    for d in sorted(cache_dir.rglob("*"), reverse=True):
        if d.is_dir():
            try:
                d.rmdir()
            except OSError:
                pass
    return count
