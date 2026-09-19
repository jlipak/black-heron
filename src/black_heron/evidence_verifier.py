"""Evidence-presence check — confirms cited evidence is in the input bundle.

A finding's `evidence` field must quote verbatim from the source samples or
entry-points. This module performs a simple substring presence check before
the LLM-based adversarial verifier runs.

If evidence is not present in the bundle, the finding is marked as suspect
(`evidence_in_bundle: false`) and the verifier prompt explicitly invites
rejection on those grounds. This catches fabricated quotes (the failure mode
documented in lesson_audit_verification.md).
"""
from __future__ import annotations

import re

from ._models import Finding, RepoContext


def _norm(s: str) -> str:
    """Collapse whitespace + lowercase for fuzzy substring check."""
    return re.sub(r"\s+", " ", s).lower().strip()


def check_evidence_in_context(
    findings: list[Finding],
    ctx: RepoContext,
) -> dict[int, bool]:
    """Returns {finding_index: evidence_was_found_in_context}."""
    # Build the haystack from all sample contents + entry-point contents
    haystack_parts = list(ctx.sample_files.values())
    haystack_parts.extend(ep.content for ep in ctx.entry_points)
    haystack = _norm("\n".join(haystack_parts))

    result: dict[int, bool] = {}
    for i, f in enumerate(findings):
        if not f.evidence.strip():
            # Empty evidence — let verifier handle
            result[i] = True
            continue
        # Normalize quoted evidence then check substring presence
        needle = _norm(f.evidence)
        # Strip common formatting (backticks, leading/trailing whitespace)
        needle = needle.strip("` ")
        if len(needle) < 20:
            # Very short evidence — too noisy to substring-match reliably
            result[i] = True
            continue
        # Try full match, then prefix (first 60 chars) as fallback
        if needle in haystack:
            result[i] = True
        elif needle[:60] in haystack:
            result[i] = True
        else:
            result[i] = False
    return result
