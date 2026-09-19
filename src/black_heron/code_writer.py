"""Code-writing (suggest mode) — drafts patches for verified P0/P1 findings.

Suggest-only in v1.2. No auto-apply. A human reviews + applies manually.

Pipeline:
  1. Receive verified findings (post-synthesis).
  2. Filter to P0/P1 with confidence >= 0.85.
  3. For each, read the affected file fully (not just sample chunk).
  4. Generate unified-diff patch via Opus 4.6.
  5. Verifier sub-pass (Opus 4.7): does this patch address the finding? Does it
     introduce new issues? Set verifier_approved = bool.
  6. Return SuggestedPatch list. Caller embeds in REPORT.md and findings.json.

Sacred Laws applicable:
  - Law I (no fabrication): patch lines MUST come from re-reading the cited file.
  - Law VIII (verifier on different model): writer = Opus 4.6, verifier = Opus 4.7.
  - Law VII (theoretical vs observable): patch addresses ACTUAL evidence, not
    hypothetical issues.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import anthropic

from ._models import SuggestedPatch
from .cost_tracker import CostTracker, record_response

WRITER_MODEL = "claude-opus-4-6"
VERIFIER_MODEL = "claude-opus-4-7"

WRITER_SYSTEM = """You are the code-writer of the Black Heron audit pipeline.

You receive a verified finding with `file`, `lines`, `claim`, `evidence`, `why_it_matters`.
Your job: produce a unified-diff patch that addresses the finding.

Discipline:
- You will receive the file's full current content. Read it carefully.
- The patch MUST be minimal — touch only what the finding identifies, nothing else.
- Match the file's existing style (indentation, quote style, naming).
- NEVER introduce new dependencies. NEVER add comments unless the WHY is non-obvious.
- NEVER refactor unrelated code "while we're here." Surgical only (Karpathy 3).
- If the finding is too abstract for a concrete patch (architectural concern, multi-file
  refactor needed), return an empty diff with `rationale` explaining why.
- Risk assessment (low/medium/high) reflects blast radius: low = single line in non-critical
  path, medium = function signature change, high = touches data shape or API boundary.

Output ONE JSON object exactly:
{
  "diff": "<unified diff text starting with --- and +++, OR empty string if no patch>",
  "rationale": "<one-two sentence why this patch addresses the finding>",
  "risk": "low|medium|high",
  "confidence": <float 0.0-1.0>
}
"""

VERIFIER_PATCH_SYSTEM = """You are the patch verifier of the Black Heron code-writer.

You receive a proposed patch + the original finding + the file's full content.
Your job: ADVERSARIAL review.

Check:
- Does the patch actually address the cited finding?
- Does the patch introduce NEW bugs visible in the surrounding context?
- Is the diff syntactically valid (matches actual file lines)?
- Is the risk assessment accurate?

Output ONE JSON object exactly:
{
  "approved": <true|false>,
  "reason": "<one sentence verdict>"
}
"""


def suggest_patches(
    findings: list[dict],
    repo_path: Path,
    client: anthropic.Anthropic,
    tracker: CostTracker | None = None,
    confidence_floor: float = 0.85,
) -> list[SuggestedPatch]:
    """For each high-confidence verified P0/P1 finding, draft a patch + verify it."""
    out: list[SuggestedPatch] = []
    for f in findings:
        sev = f.get("severity", "P2")
        conf = float(f.get("confidence", 0.0))
        if sev not in ("P0", "P1") or conf < confidence_floor:
            continue
        try:
            patch = _draft_patch(f, repo_path, client, tracker)
        except Exception as e:
            sys.stderr.write(f"[code_writer] draft failed for {f.get('file')}: {e}\n")
            continue
        if patch is None:
            continue
        try:
            patch.verifier_approved = _verify_patch(f, patch, repo_path, client, tracker)
        except Exception as e:
            sys.stderr.write(f"[code_writer] verify failed for {f.get('file')}: {e}\n")
            patch.verifier_approved = False
        out.append(patch)
    return out


def _draft_patch(
    finding: dict,
    repo_path: Path,
    client: anthropic.Anthropic,
    tracker: CostTracker | None,
) -> SuggestedPatch | None:
    file_rel = finding.get("file", "")
    file_abs = (repo_path / file_rel).resolve()
    try:
        file_content = file_abs.read_text(encoding="utf-8")
    except OSError:
        return None
    # Cap content at 20KB to prevent prompt overflow
    if len(file_content) > 20000:
        file_content = file_content[:20000] + "\n[... truncated at 20KB]"

    user = (
        f"# Finding\n"
        f"Lens: {finding.get('lens')}\n"
        f"Severity: {finding.get('severity')}\n"
        f"File: {file_rel}\n"
        f"Lines: {finding.get('lines')}\n"
        f"Claim: {finding.get('claim')}\n"
        f"Evidence:\n```\n{finding.get('evidence', '')}\n```\n"
        f"Why it matters: {finding.get('why_it_matters')}\n\n"
        f"# Current file content ({file_rel})\n```\n{file_content}\n```\n\n"
        f"Now produce the JSON patch object."
    )

    response = client.messages.create(
        model=WRITER_MODEL,
        max_tokens=4096,
        system=[{"type": "text", "text": WRITER_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    if tracker is not None:
        record_response(tracker, response, model=WRITER_MODEL, lens_name="code_writer")

    text = "".join(getattr(b, "text", "") for b in response.content)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    diff = (data.get("diff") or "").strip()
    if not diff:
        return None
    return SuggestedPatch(
        file=file_rel,
        lines_old=finding.get("lines", "?"),
        diff=diff,
        rationale=data.get("rationale", ""),
        risk=data.get("risk", "medium"),
        confidence=float(data.get("confidence", 0.0)),
        verifier_approved=False,
    )


def _verify_patch(
    finding: dict,
    patch: SuggestedPatch,
    repo_path: Path,
    client: anthropic.Anthropic,
    tracker: CostTracker | None,
) -> bool:
    file_rel = finding.get("file", "")
    file_abs = (repo_path / file_rel).resolve()
    try:
        file_content = file_abs.read_text(encoding="utf-8")
    except OSError:
        return False
    if len(file_content) > 20000:
        file_content = file_content[:20000] + "\n[... truncated]"

    user = (
        f"# Original finding\n"
        f"Severity: {finding.get('severity')}\n"
        f"File: {file_rel} lines {finding.get('lines')}\n"
        f"Claim: {finding.get('claim')}\n\n"
        f"# Proposed patch\n"
        f"Risk: {patch.risk}\nRationale: {patch.rationale}\n```diff\n{patch.diff}\n```\n\n"
        f"# Current file content\n```\n{file_content}\n```\n\n"
        f"Approve or reject."
    )

    response = client.messages.create(
        model=VERIFIER_MODEL,
        max_tokens=512,
        system=[{"type": "text", "text": VERIFIER_PATCH_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    if tracker is not None:
        record_response(tracker, response, model=VERIFIER_MODEL, lens_name="patch_verifier")

    text = "".join(getattr(b, "text", "") for b in response.content)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return False
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return False
    return bool(data.get("approved", False))
