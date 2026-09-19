"""Blind-spot lens — meta-intersection issues the other 3 lenses miss.

Apollo audit lesson: blind-spot hunter produces highest marginal value because
domain-specialized lenses (security, types, data) cover their own surface but
miss intersections — PII in observability, secrets in commits, etc.
"""
from __future__ import annotations

import anthropic

from .._models import Finding, RepoContext
from ..cost_tracker import CostTracker, record_response
from ._common import build_repo_prompt, parse_findings

LENS_NAME = "blind_spot"
MODEL = "claude-opus-4-8"

SYSTEM = """You are the blind-spot lens of the Black Heron repository audit. You run LAST, after code_quality, governance, and drift have already produced findings.

Your job is NOT to add more findings of the kind those lenses already cover. Your job is to find what they MISS — issues that fall in the intersection between two domains, not inside any single lens's natural reach.

Examples of meta-intersection issues:

- **PII in observability** (data × logs): logs.info(`user signed in: ${email}`) — data lens doesn't audit logs; observability lens doesn't audit data shape
- **Secrets in commit messages or git history** (config × VCS): "added api key for X" in commit message — secret-scanning lens doesn't read commit messages
- **TODO referencing a feature that never landed** (drift × dead-promise): commit "TODO: revisit caching strategy after v2" — no v2 in roadmap
- **Threshold magic number duplicated across files with different values** (config × consistency): one file says `MAX_RETRIES = 3`, sibling says `MAX_RETRIES = 5`
- **Documented feature has no production code path** (drift × architecture): README documents flag `--encrypt` — flag not parsed in cli.py
- **Test asserts behavior that source does not implement** (test × code drift): test expects `function returns null on empty input` — function actually throws
- **Error message references a config key that has been removed** (drift × UX): error: "set REDIS_URL" — `REDIS_URL` is no longer read anywhere
- **Schema field used in serialization but never in deserialization or vice versa** (consistency × correctness): producer writes `audit.cost`; consumer never reads it

Discipline:
- You receive a list of findings already produced by code_quality, governance, drift. Read them. Do NOT duplicate them.
- Only raise findings that span 2+ domains. Single-domain noise is NOT in your scope.
- NEVER fabricate. The "File listing" + "Entry-point files" + "Source samples" sections are the authoritative input. Cite from them.
- If you can't find a genuine intersection issue, return an empty findings array. That is a valid result.

Severity rules apply (same as other lenses):
- P0 — material correctness/security/compliance violation spanning 2+ domains
- P1 — durable maintainability gap that none of the single-domain lenses can flag alone
- P2 — minor meta-consistency note

For each finding:
- If confidence < 0.6, you MUST include a non-empty `uncertainty_reason` field.
- Set `absence_claim: true` if asserting a feature/file is missing.
- In `claim`, explicitly name BOTH domains the issue spans (e.g., "(observability × data shape)").

Output ONE JSON object exactly. Schema same as other lenses, with `lens: "blind_spot"`.
"""


def run(
    ctx: RepoContext,
    findings_so_far: list[Finding],
    client: anthropic.Anthropic,
    tracker: CostTracker | None = None,
    model: str | None = None,
) -> list[Finding]:
    model = model or MODEL
    base = build_repo_prompt(ctx)
    findings_block = _render_prior_findings(findings_so_far)
    user = f"{base}\n\n## Findings produced by other lenses (do NOT duplicate)\n\n{findings_block}"

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    if tracker is not None:
        record_response(tracker, response, model=model, lens_name=LENS_NAME)
    text = "".join(getattr(b, "text", "") for b in response.content)
    return parse_findings(text, LENS_NAME)


def _render_prior_findings(findings: list[Finding]) -> str:
    if not findings:
        return "(No findings from other lenses — repo looks clean to them, focus on meta-intersection gaps that single-lens checks miss by design.)"
    out = []
    for i, f in enumerate(findings, 1):
        out.append(
            f"{i}. [{f.lens}/{f.severity}] {f.file} {f.lines}: {f.claim}"
        )
    return "\n".join(out)
