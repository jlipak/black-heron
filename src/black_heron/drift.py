"""Baseline drift mode — set-difference categorization of audit findings over time.

Phase R is intentionally deterministic. No LLM call. The "drift" is observable:
two findings collapse to the same `identity_hash` iff they refer to the same
issue at the same place; bucket assignment is set arithmetic on those hashes.
Law VII: distinguish theoretical from observable — drift IS observable.

Identity heuristic:
    sha256(lens + "|" + file + "|" + normalized_lines + "|" + first_8_words(claim))

`normalized_lines` strips the "L" prefix and takes only the start line ("L42-L88"
collapses to "42"). `first_8_words(claim)` lowercases the claim, drops
punctuation, keeps the first 8 word tokens — robust to LLM rephrasing of
the same underlying issue.

Drift triggers (any one moves a finding to the `drifted` bucket):
- severity changed (P0↔P1↔P2)
- confidence delta > 0.2 in either direction
- evidence string is not a substring-equal match

Baseline parsing is defensive (Law V: never claim absence without checking the
authoritative source). A missing or unparseable baseline yields a DriftReport
with `available=False` and a `skipped_reason`; the audit continues without
the drift section.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_WS_RE = re.compile(r"\s+", re.UNICODE)
_CONFIDENCE_DELTA_THRESHOLD = 0.2  # any |Δconf| above this triggers `drifted`


@dataclass
class DriftReport:
    """Result of set-difference categorization on identity hash.

    `available=False` plus `skipped_reason` indicates baseline could not be
    loaded; callers should NOT render a drift section in that case, but should
    surface the skip note in REPORT.md so absence is honest (Law V).
    """

    available: bool = False
    skipped_reason: str | None = None
    baseline_path: str | None = None
    baseline_generated_at: str | None = None
    new: list[dict] = field(default_factory=list)
    closed: list[dict] = field(default_factory=list)
    persisting: list[dict] = field(default_factory=list)
    drifted: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "new": len(self.new),
            "closed": len(self.closed),
            "persisting": len(self.persisting),
            "drifted": len(self.drifted),
        }

    def to_payload(self) -> dict:
        """Render as the `baseline_diff` block written into findings.json."""
        return {
            "available": self.available,
            "skipped_reason": self.skipped_reason,
            "baseline_path": self.baseline_path,
            "baseline_generated_at": self.baseline_generated_at,
            "counts": self.counts(),
            "new": self.new,
            "closed": self.closed,
            "persisting": self.persisting,
            "drifted": self.drifted,
        }


def _normalize_lines(line_str: Any) -> str:
    if not isinstance(line_str, str):
        return ""
    s = line_str.strip()
    if not s:
        return ""
    # accept "L42", "L42-L88", "L42-88", "42", "42-88", "L42,L88", "commits"
    head = s.split(",")[0].split("-")[0]
    head = head.lstrip("Ll")
    if head.isdigit():
        return head
    return head.lower()


def _first_8_words(claim: Any) -> str:
    if not isinstance(claim, str):
        return ""
    cleaned = _PUNCT_RE.sub(" ", claim.lower())
    tokens = _WS_RE.sub(" ", cleaned).strip().split(" ")
    return " ".join(tokens[:8])


def compute_identity_hash(finding: dict) -> str:
    """Deterministic identity for a finding (lens + file + start-line + claim-prefix).

    Two findings collapse to the same hash iff a reasonable human would call
    them the same issue. The first-8-words rule is robust to small LLM
    rephrasings; the line-start collapse handles "L42" vs "L42-L88" drift.
    """
    parts = [
        str(finding.get("lens", "")),
        str(finding.get("file", "")),
        _normalize_lines(finding.get("lines")),
        _first_8_words(finding.get("claim")),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _evidence_changed(current: dict, baseline: dict) -> bool:
    a = (current.get("evidence") or "").strip()
    b = (baseline.get("evidence") or "").strip()
    if not a and not b:
        return False
    # treat as unchanged if one is a substring of the other (LLM may
    # broaden/narrow the quote without the issue actually changing)
    if a == b or a in b or b in a:
        return False
    return True


def _drift_reasons(current: dict, baseline: dict) -> list[str]:
    reasons: list[str] = []
    sev_c = current.get("severity")
    sev_b = baseline.get("severity")
    if sev_c != sev_b:
        reasons.append(f"severity:{sev_b}->{sev_c}")
    try:
        conf_c = float(current.get("confidence", 0.0))
        conf_b = float(baseline.get("confidence", 0.0))
        if abs(conf_c - conf_b) > _CONFIDENCE_DELTA_THRESHOLD:
            reasons.append(f"confidence:{conf_b:.2f}->{conf_c:.2f}")
    except (TypeError, ValueError):
        pass
    if _evidence_changed(current, baseline):
        reasons.append("evidence:changed")
    return reasons


def categorize(
    current: list[dict],
    baseline: list[dict],
    *,
    baseline_path: str | None = None,
    baseline_generated_at: str | None = None,
) -> DriftReport:
    """Set-difference categorization on identity hash.

    Pure function. No I/O. Hashes computed inline so a malformed finding (no
    lens / no file / no claim) still produces a deterministic — if poor —
    hash; that ensures it can be categorized rather than dropped silently.
    """
    current_index: dict[str, dict] = {}
    for f in current:
        h = compute_identity_hash(f)
        # last write wins is fine — duplicate hashes inside one audit are rare
        f_with_hash = dict(f)
        f_with_hash["identity_hash"] = h
        current_index[h] = f_with_hash
    baseline_index: dict[str, dict] = {}
    for f in baseline:
        h = compute_identity_hash(f)
        f_with_hash = dict(f)
        f_with_hash["identity_hash"] = h
        baseline_index[h] = f_with_hash

    new_keys = set(current_index) - set(baseline_index)
    closed_keys = set(baseline_index) - set(current_index)
    common_keys = set(current_index) & set(baseline_index)

    new_list = [current_index[h] for h in sorted(new_keys)]
    closed_list = [baseline_index[h] for h in sorted(closed_keys)]
    persisting: list[dict] = []
    drifted: list[dict] = []
    for h in sorted(common_keys):
        cur = current_index[h]
        base = baseline_index[h]
        reasons = _drift_reasons(cur, base)
        if reasons:
            drifted.append({
                "identity_hash": h,
                "drift_reasons": reasons,
                "current": cur,
                "baseline": base,
            })
        else:
            persisting.append(cur)

    return DriftReport(
        available=True,
        baseline_path=baseline_path,
        baseline_generated_at=baseline_generated_at,
        new=new_list,
        closed=closed_list,
        persisting=persisting,
        drifted=drifted,
    )


def load_baseline_findings(path: Path) -> tuple[list[dict], str | None, str | None]:
    """Defensive baseline loader.

    Returns (findings_list, generated_at_or_None, error_or_None). The list is
    always a list — empty on any failure. Error is a one-line description for
    REPORT.md when the baseline could not be loaded; None on success.

    Accepts both shapes:
        {"verified": [...], ...}                       # full Black Heron findings.json
        {"findings": [...]}                            # generic / verifier-output shape
        [...]                                           # bare list of findings
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        return [], None, f"baseline file unreadable: {e}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return [], None, f"baseline JSON malformed: {e}"

    generated_at: str | None = None
    findings: list[dict] | None = None
    if isinstance(data, list):
        findings = [f for f in data if isinstance(f, dict)]
    elif isinstance(data, dict):
        generated_at = data.get("generated_at_utc") if isinstance(data.get("generated_at_utc"), str) else None
        for key in ("verified", "findings"):
            v = data.get(key)
            if isinstance(v, list):
                findings = [f for f in v if isinstance(f, dict)]
                break
    if findings is None:
        return [], generated_at, "baseline JSON has no recognizable findings array (expected list, or {'verified': [...]}, or {'findings': [...]})"

    return findings, generated_at, None


def compute_drift_from_file(
    current_findings: list[dict],
    baseline_path: Path | None,
) -> DriftReport:
    """Top-level convenience: load baseline file + categorize.

    Returns a DriftReport with `available=False` and `skipped_reason` when the
    baseline path is missing, unreadable, or unparseable. Audit pipeline must
    proceed regardless (Law IV — partial result is honest, crash is not).
    """
    if baseline_path is None:
        return DriftReport(available=False, skipped_reason="no --baseline path supplied")
    if not baseline_path.is_file():
        return DriftReport(
            available=False,
            baseline_path=str(baseline_path),
            skipped_reason="baseline path does not exist or is not a file",
        )
    findings, generated_at, err = load_baseline_findings(baseline_path)
    if err is not None:
        print(f"[bh:drift] baseline skip: {err}", file=sys.stderr)
        return DriftReport(
            available=False,
            baseline_path=str(baseline_path),
            baseline_generated_at=generated_at,
            skipped_reason=err,
        )
    return categorize(
        current_findings,
        findings,
        baseline_path=str(baseline_path),
        baseline_generated_at=generated_at,
    )
