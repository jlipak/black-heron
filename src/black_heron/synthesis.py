"""Adversarial verifier — Opus reads all findings, kills FPs, ranks the rest."""
from __future__ import annotations

import json
import sys

import anthropic
from pydantic import BaseModel, ConfigDict

from ._models import Finding, RepoContext, Rubric
from .cost_tracker import CostTracker, record_response
from .evidence_verifier import check_evidence_in_context

MODEL = "claude-opus-4-7"


SYSTEM = """You are the adversarial verifier in the Black Heron audit pipeline.

You receive a set of findings produced by four independent lenses (code_quality, governance, drift, blind_spot). Each finding may carry an `evidence_in_bundle` flag indicating whether the cited evidence string was found verbatim in the input bundle. Treat `evidence_in_bundle: false` as strong prior for REJECT (fabricated evidence).

Your job is NOT to add findings. Your job is to CHALLENGE them.

For each finding, decide one of:
- KEEP — finding is well-supported by its cited evidence, severity matches the claim, the audit reader benefits from seeing it.
- REJECT — finding is fabricated (no real evidence in bundle), overstated (cited evidence doesn't support the severity), duplicates another finding, or is purely theoretical (the cited evidence doesn't show the issue is observable).
- DOWNGRADE — finding is real but the severity is too high (e.g., labeled P0 when the cited evidence supports only P1, or `absence_claim: true` finding where the cited authoritative section is incomplete).

Apply severity confidence floors strictly:
- P0 requires confidence ≥ 0.85; downgrade to P1 if 0.70 ≤ conf < 0.85
- P1 requires confidence ≥ 0.70; downgrade to P2 if 0.50 ≤ conf < 0.70
- P2 requires confidence ≥ 0.50; REJECT if conf < 0.50 and no compensating explicit evidence

Treat `absence_claim: true` findings extra-skeptically: the lens claimed a file or feature is missing. Verify by checking whether the file listing AND entry-point contents could plausibly contain the asserted item. If the lens didn't check both authoritative sources, REJECT or DOWNGRADE.

You also produce ONE field called `verifier_note` per finding — one sentence explaining your verdict and (for DOWNGRADE) what would have justified the original severity.

Output ONE JSON object exactly:
{
  "verified": [
    {
      "lens": "...",
      "severity": "P0" | "P1" | "P2",
      "file": "...",
      "lines": "...",
      "claim": "...",
      "evidence": "...",
      "why_it_matters": "...",
      "confidence": 0.0-1.0,
      "verifier_note": "<one sentence>"
    }
  ],
  "rejected": [
    {
      "claim": "<verbatim from rejected finding>",
      "reason": "<one sentence>"
    }
  ]
}
"""


class VerifierResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    verified: list[dict]
    rejected: list[dict] = []


def synthesize(
    ctx: RepoContext,
    findings: list[Finding],
    client: anthropic.Anthropic,
    tracker: CostTracker | None = None,
    rubric: Rubric | None = None,
) -> VerifierResult:
    """Run evidence presence check + Opus adversarial verifier + post-filter by confidence floor."""

    # Kill-switch
    cap = rubric.kill_switch_total_findings_cap if rubric else 50
    high_sev = sum(1 for f in findings if f.severity in ("P0", "P1"))
    if high_sev > cap:
        raise RuntimeError(
            f"Kill-switch triggered: {high_sev} P0/P1 findings exceeds cap of {cap}. "
            f"Verify lens prompts before re-running."
        )

    if not findings:
        return VerifierResult(verified=[], rejected=[])

    # Evidence presence check (pre-LLM)
    evidence_check = check_evidence_in_context(findings, ctx)
    fabricated_count = sum(1 for v in evidence_check.values() if not v)
    if fabricated_count:
        print(
            f"[BH] {fabricated_count}/{len(findings)} findings have cited evidence not found in input bundle "
            f"(possible fabrication). Verifier will see flags.",
            file=sys.stderr,
        )

    user = _build_verifier_prompt(ctx, findings, evidence_check)
    response = client.messages.create(
        model=MODEL,
        max_tokens=16384,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    if tracker is not None:
        record_response(tracker, response, model=MODEL, lens_name="verifier")

    text = "".join(getattr(b, "text", "") for b in response.content)
    result = _parse_verifier(text)

    # Post-filter: enforce severity confidence floors if rubric given
    if rubric is not None and result.verified:
        result.verified = _apply_confidence_floors(result.verified, rubric)

    # Fallback if verifier output unparseable
    if not result.verified and not result.rejected and findings:
        print(
            f"[BH] Verifier returned unparseable / empty output "
            f"(stop_reason={response.stop_reason}, raw len={len(text)}). "
            f"Falling back to raw lens findings with confidence cap.",
            file=sys.stderr,
        )
        fallback = []
        for f in findings:
            d = f.model_dump()
            d["verifier_note"] = "verifier output unparseable; raw lens finding preserved as best-effort"
            d["confidence"] = min(d.get("confidence", 0.5), 0.5)
            fallback.append(d)
        return VerifierResult(verified=fallback, rejected=[])

    return result


def _build_verifier_prompt(
    ctx: RepoContext,
    findings: list[Finding],
    evidence_check: dict[int, bool],
) -> str:
    parts = [
        f"# Repository under audit: {ctx.path}",
        f"Files: {ctx.file_count} | Primary language: {ctx.primary_language} | TODOs: {ctx.todo_count}",
        f"Entry-point files loaded: {[ep.path for ep in ctx.entry_points]}",
        "",
        f"## Findings to verify ({len(findings)} total)",
    ]
    for i, f in enumerate(findings):
        ev_ok = evidence_check.get(i, True)
        absence = " [absence_claim]" if f.absence_claim else ""
        uncert = f"\nUncertainty: {f.uncertainty_reason}" if f.uncertainty_reason else ""
        evidence_flag = "" if ev_ok else "\n**evidence_in_bundle: false** — cited evidence NOT found verbatim in input bundle; treat as strong prior for REJECT."
        parts.append(
            f"\n### Finding {i+1} ({f.lens}, {f.severity}, confidence={f.confidence:.2f}){absence}\n"
            f"File: `{f.file}` lines {f.lines}\n"
            f"Claim: {f.claim}\n"
            f"Evidence:\n```\n{f.evidence}\n```\n"
            f"Why it matters: {f.why_it_matters}{uncert}{evidence_flag}"
        )
    parts.append(
        "\nNow produce the JSON verdict. Be skeptical — false positives in an audit "
        "report damage the reviewer's trust more than missed real issues. "
        "Apply severity confidence floors and reject fabricated-evidence findings without mercy."
    )
    return "\n".join(parts)


def _parse_verifier(text: str) -> VerifierResult:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return VerifierResult(verified=[], rejected=[])
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return VerifierResult(verified=[], rejected=[])
    return VerifierResult(**data)


def _apply_confidence_floors(verified: list[dict], rubric: Rubric) -> list[dict]:
    """Final guard: if a finding leaks through with confidence below the floor for its severity, downgrade or drop."""
    floors = rubric.severity_confidence_floors
    out: list[dict] = []
    for f in verified:
        sev = f.get("severity", "P2")
        conf = float(f.get("confidence", 0.0))
        floor = floors.get(sev, 0.5)
        if conf >= floor:
            out.append(f)
            continue
        # Try downgrade
        if sev == "P0" and conf >= floors.get("P1", 0.7):
            f["severity"] = "P1"
            f["verifier_note"] = (
                (f.get("verifier_note", "") + " | post-filter downgraded P0→P1 (confidence below P0 floor)").strip(" |")
            )
            out.append(f)
        elif sev == "P1" and conf >= floors.get("P2", 0.5):
            f["severity"] = "P2"
            f["verifier_note"] = (
                (f.get("verifier_note", "") + " | post-filter downgraded P1→P2 (confidence below P1 floor)").strip(" |")
            )
            out.append(f)
        else:
            # Drop (it's recorded conceptually in raw_counts; readers see the filtered list)
            continue
    return out
