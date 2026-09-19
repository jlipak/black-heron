"""Render the verified findings into Markdown + JSON + SARIF."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ._models import RepoContext
from .synthesis import VerifierResult

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
SARIF_LEVEL = {"P0": "error", "P1": "warning", "P2": "note"}
BLACK_HERON_VERSION = "1.3.3"


def write_report(
    out_dir: Path,
    ctx: RepoContext,
    verifier: VerifierResult,
    lens_raw_counts: dict[str, int],
    metrics: dict | None = None,
    suggested_patches: list[dict] | None = None,
    baseline_diff: dict | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = metrics or {}
    patches = suggested_patches or []
    bd = baseline_diff or {"available": False}
    _write_findings_json(out_dir / "findings.json", ctx, verifier, lens_raw_counts, metrics, patches, bd)
    _write_findings_sarif(out_dir / "findings.sarif", ctx, verifier)
    _write_report_md(out_dir / "REPORT.md", ctx, verifier, lens_raw_counts, metrics, patches, bd)


def _write_findings_json(
    path: Path,
    ctx: RepoContext,
    v: VerifierResult,
    raw: dict,
    metrics: dict,
    patches: list[dict],
    baseline_diff: dict,
) -> None:
    payload = {
        "schema_version": "1.0.0",
        "black_heron_version": BLACK_HERON_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "repo": {
            "path": ctx.path,
            "file_count": ctx.file_count,
            "primary_language": ctx.primary_language,
            "todo_count": ctx.todo_count,
            "entry_points_loaded": [ep.path for ep in ctx.entry_points],
        },
        "metrics": metrics,
        "lens_raw_counts": raw,
        "verified_count": len(v.verified),
        "rejected_count": len(v.rejected),
        "verified": v.verified,
        "rejected": v.rejected,
        "suggested_patches": patches,
        "baseline_diff": baseline_diff,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_findings_sarif(path: Path, ctx: RepoContext, v: VerifierResult) -> None:
    """Minimal viable SARIF 2.1.0 — GitHub Code Scanning compatible."""
    rules_seen: dict[str, dict] = {}
    results: list[dict] = []
    for f in v.verified:
        lens = f.get("lens", "unknown")
        severity = f.get("severity", "P2")
        rule_id = f"BH/{lens}/{severity}"
        if rule_id not in rules_seen:
            rules_seen[rule_id] = {
                "id": rule_id,
                "name": f"{lens}-{severity}",
                "shortDescription": {"text": f"{lens} lens, severity {severity}"},
                "defaultConfiguration": {"level": SARIF_LEVEL.get(severity, "note")},
            }
        line_str = f.get("lines", "L1")
        start_line = _parse_start_line(line_str)
        results.append({
            "ruleId": rule_id,
            "level": SARIF_LEVEL.get(severity, "note"),
            "message": {"text": f.get("claim", "")},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": f.get("file", "")},
                    "region": {"startLine": start_line},
                }
            }],
            "properties": {
                "confidence": f.get("confidence", 0),
                "lens": lens,
                "severity": severity,
                "why_it_matters": f.get("why_it_matters", ""),
                "verifier_note": f.get("verifier_note", ""),
            },
        })

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "Black Heron",
                    "version": BLACK_HERON_VERSION,
                    "informationUri": "https://github.com/jlipak/black-heron",
                    "rules": list(rules_seen.values()),
                }
            },
            "results": results,
            "originalUriBaseIds": {"%SRCROOT%": {"uri": Path(ctx.path).as_uri() + "/"}},
        }],
    }
    path.write_text(json.dumps(sarif, indent=2), encoding="utf-8")


def _render_drift_section(lines: list[str], baseline_diff: dict) -> None:
    """Render 'Drift since baseline' immediately after the Summary block.

    Schema follows DriftReport.to_payload(): `available`, `skipped_reason`,
    `baseline_path`, `baseline_generated_at`, `counts`, `new`, `closed`,
    `persisting`, `drifted`. When `available` is False, we still surface the
    skipped reason so silent absence is impossible (Law V).
    """
    if not baseline_diff:
        return
    if not baseline_diff.get("available"):
        reason = baseline_diff.get("skipped_reason")
        if reason and baseline_diff.get("baseline_path"):
            lines.append("## Drift since baseline")
            lines.append("")
            lines.append(
                f"Baseline path supplied (`{baseline_diff.get('baseline_path')}`) "
                f"but drift was skipped: **{reason}**. Audit completed without a drift section."
            )
            lines.append("")
        return

    counts = baseline_diff.get("counts") or {}
    new = baseline_diff.get("new") or []
    closed = baseline_diff.get("closed") or []
    persisting = baseline_diff.get("persisting") or []
    drifted = baseline_diff.get("drifted") or []
    baseline_path = baseline_diff.get("baseline_path") or "(unknown)"
    baseline_ts = baseline_diff.get("baseline_generated_at") or "(unknown timestamp)"

    lines.append("## Drift since baseline")
    lines.append("")
    lines.append(f"**Baseline:** `{baseline_path}` (generated {baseline_ts})")
    lines.append("")
    lines.append("| Bucket | Count | Note |")
    lines.append("|---|---|---|")
    lines.append(f"| New | {counts.get('new', len(new))} | First seen this run |")
    lines.append(
        f"| Closed | {counts.get('closed', len(closed))} | Present in baseline, gone now (verify in `git log`) |"
    )
    lines.append(
        f"| Persisting | {counts.get('persisting', len(persisting))} | Same severity since baseline — accumulating debt if P0/P1 |"
    )
    lines.append(
        f"| Drifted | {counts.get('drifted', len(drifted))} | Identity match but severity/confidence/evidence changed |"
    )
    lines.append("")

    # Persisting P0/P1 callout — governance signal
    p0_p1_persist = [f for f in persisting if f.get("severity") in ("P0", "P1")]
    if p0_p1_persist:
        lines.append(
            f"**Compliance debt signal:** {len(p0_p1_persist)} P0/P1 finding(s) persist since baseline. "
            f"Each persisting high-severity finding is one audit-cycle of unfixed risk."
        )
        lines.append("")

    if new:
        lines.append(f"### New findings ({len(new)})")
        lines.append("")
        for i, f in enumerate(new, 1):
            lines.append(
                f"- **{i}.** [{f.get('lens', '?')}/{f.get('severity', '?')}] "
                f"`{f.get('file', '?')}` lines `{f.get('lines', '?')}`: {f.get('claim', '?')}"
            )
        lines.append("")

    if closed:
        lines.append(f"### Closed findings ({len(closed)})")
        lines.append("")
        lines.append(
            "_Closed findings should correspond to fixes in `git log`. If you don't see a commit "
            "between baseline and now that touches the referenced file, the finding may have been "
            "masked (rephrased / dropped by a lens) rather than fixed — investigate before treating "
            "as resolved._"
        )
        lines.append("")
        for i, f in enumerate(closed, 1):
            lines.append(
                f"- **{i}.** [{f.get('lens', '?')}/{f.get('severity', '?')}] "
                f"`{f.get('file', '?')}` lines `{f.get('lines', '?')}`: {f.get('claim', '?')}"
            )
        lines.append("")

    if drifted:
        lines.append(f"### Drifted findings ({len(drifted)})")
        lines.append("")
        lines.append(
            "_Identity matches the baseline finding but severity, confidence, or evidence has shifted. "
            "Severity de-escalation (P1 → P2) without a corresponding fix commit is often LLM noise; "
            "verify against `git log`._"
        )
        lines.append("")
        for i, d in enumerate(drifted, 1):
            cur = d.get("current") or {}
            base = d.get("baseline") or {}
            reasons = d.get("drift_reasons") or []
            lines.append(
                f"- **{i}.** `{cur.get('file', '?')}` lines `{cur.get('lines', '?')}`: "
                f"{cur.get('claim', '?')}"
            )
            lines.append(
                f"  - baseline: severity={base.get('severity', '?')}, confidence={base.get('confidence', '?')}"
            )
            lines.append(
                f"  - current : severity={cur.get('severity', '?')}, confidence={cur.get('confidence', '?')}"
            )
            lines.append(f"  - drift reasons: {', '.join(reasons) if reasons else '(none cited)'}")
        lines.append("")


def _parse_start_line(line_str: str) -> int:
    """Extract integer start line from 'L42', 'L42-L88', 'commits', etc."""
    if not line_str:
        return 1
    s = line_str.lstrip("L").split("-")[0].lstrip("L")
    try:
        return max(1, int(s))
    except (ValueError, TypeError):
        return 1


def _volume_summary(verified_count: int, rejected_count: int, p0: int, p1: int, p2: int) -> str:
    """Calibrate the lead-in sentence to the actual volume + severity mix."""
    if verified_count == 0:
        return "This audit found **no substantive issues** that survived the adversarial verifier. The repo passes this pass."
    if p0 > 0 and verified_count <= 5:
        return f"This audit surfaced **{verified_count} substantive issues**, including **{p0} P0**. Small set — recommend addressing P0 first."
    if verified_count <= 5:
        return f"This audit surfaced **{verified_count} issues**, no P0. The repo looks healthy; addresses are quality-of-life."
    if verified_count <= 15:
        return f"This audit surfaced **{verified_count} issues** across multiple lenses ({p0} P0 / {p1} P1 / {p2} P2). Review priority order; the verifier filtered {rejected_count} additional noise candidates."
    return f"This audit surfaced **{verified_count} issues** — significant volume ({p0} P0 / {p1} P1 / {p2} P2) warrants triage. The verifier filtered {rejected_count} noise candidates upstream."


def _write_report_md(
    path: Path,
    ctx: RepoContext,
    v: VerifierResult,
    raw: dict,
    metrics: dict,
    patches: list[dict],
    baseline_diff: dict,
) -> None:
    by_sev: dict[str, list[dict]] = {"P0": [], "P1": [], "P2": []}
    for f in v.verified:
        sev = f.get("severity", "P2")
        by_sev.setdefault(sev, []).append(f)
    p0, p1, p2 = len(by_sev["P0"]), len(by_sev["P1"]), len(by_sev["P2"])

    lines: list[str] = []
    lines.append("# Black Heron — Audit Report")
    lines.append("")
    lines.append(f"> Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} by Black Heron v{BLACK_HERON_VERSION}")
    lines.append("")
    lines.append(f"**Repository:** `{ctx.path}`")
    lines.append(f"**Files audited:** {ctx.file_count} (primary language: {ctx.primary_language})")
    lines.append(f"**TODO markers found in source:** {ctx.todo_count}")
    lines.append(f"**Entry-point files loaded full-content:** {len(ctx.entry_points)} ({', '.join(ep.path for ep in ctx.entry_points) or 'none'})")
    lines.append("")

    # Volume-calibrated summary
    lines.append("## Summary")
    lines.append("")
    lines.append(_volume_summary(len(v.verified), len(v.rejected), p0, p1, p2))
    lines.append("")

    _render_drift_section(lines, baseline_diff)

    # Metrics block
    if metrics:
        lines.append("## Metrics")
        lines.append("")
        lines.append(f"- **Wall time:** {metrics.get('wall_seconds', '?')}s")
        lines.append(f"- **Total cost:** ${metrics.get('total_cost_usd', 0):.4f}")
        if metrics.get("per_lens_cost_usd"):
            lines.append("- **Per-lens cost (USD):**")
            for k, c in metrics["per_lens_cost_usd"].items():
                lines.append(f"  - `{k}`: ${c:.4f}")
        if metrics.get("per_lens_seconds"):
            lines.append("- **Per-lens latency (s):**")
            for k, t in metrics["per_lens_seconds"].items():
                lines.append(f"  - `{k}`: {t:.1f}s")
        lines.append(f"- **Rubric version:** `{metrics.get('rubric_version', '?')}` (source: `{metrics.get('rubric_source', '?')}`)")
        cache_info = metrics.get("cache") or {}
        if cache_info:
            if cache_info.get("enabled"):
                lines.append(
                    f"- **Cache:** {cache_info.get('hits', 0)} hit / "
                    f"{cache_info.get('misses', 0)} miss "
                    f"(dir: `{cache_info.get('cache_dir', '?')}`)"
                )
            else:
                lines.append(
                    f"- **Cache:** disabled this run ({cache_info.get('bypassed', 0)} lens calls bypassed)"
                )
        lines.append("")
        enrichment_reports = metrics.get("enrichment") or []
        if enrichment_reports:
            lines.append("### MCP enrichment")
            lines.append("")
            lines.append("| Enricher | Available | Items | Bytes | Wall (s) | Note |")
            lines.append("|---|---|---|---|---|---|")
            for r in enrichment_reports:
                lines.append(
                    f"| {r.get('name', '?')} "
                    f"| {'yes' if r.get('available') else 'no'} "
                    f"| {r.get('items_fetched', 0)} "
                    f"| {r.get('bytes_fetched', 0)} "
                    f"| {r.get('wall_seconds', 0)} "
                    f"| {r.get('skipped_reason') or 'ok'} |"
                )
            lines.append("")

    lines.append("## Lens raw output")
    lines.append("")
    lines.append("| Lens | Raw findings |")
    lines.append("|---|---|")
    for k, n in raw.items():
        lines.append(f"| {k} | {n} |")
    lines.append("")
    lines.append(f"**After adversarial verifier:** {len(v.verified)} kept, {len(v.rejected)} rejected.")
    if len(v.verified) + len(v.rejected) > 0:
        reject_ratio = len(v.rejected) / (len(v.verified) + len(v.rejected))
        lines.append(f"**Verifier reject ratio:** {reject_ratio:.1%}")
    lines.append("")

    if not v.verified:
        lines.append("## Verified findings")
        lines.append("")
        lines.append("No findings survived the verifier.")
    else:
        for sev in ("P0", "P1", "P2"):
            items = by_sev.get(sev, [])
            if not items:
                continue
            lines.append(f"## {sev} findings ({len(items)})")
            lines.append("")
            for i, f in enumerate(items, 1):
                lines.append(f"### {sev}.{i} — {f.get('claim', '(no claim)')}")
                lines.append("")
                lines.append(f"- **Lens:** {f.get('lens', '?')}")
                lines.append(f"- **File:** `{f.get('file', '?')}` lines `{f.get('lines', '?')}`")
                lines.append(f"- **Confidence:** {f.get('confidence', 0):.2f}")
                lines.append("")
                lines.append("**Evidence:**")
                lines.append("```")
                lines.append(f.get("evidence", "").strip())
                lines.append("```")
                lines.append(f"**Why it matters:** {f.get('why_it_matters', '')}")
                if f.get("verifier_note"):
                    lines.append(f"**Verifier note:** {f.get('verifier_note')}")
                lines.append("")

    if patches:
        approved = [p for p in patches if p.get("verifier_approved")]
        lines.append(f"## Suggested patches ({len(approved)}/{len(patches)} verifier-approved)")
        lines.append("")
        lines.append("These patches are SUGGESTIONS only — a human reviews + applies manually. Never auto-applied.")
        lines.append("")
        for i, p in enumerate(patches, 1):
            badge = "✓ verifier-approved" if p.get("verifier_approved") else "⚠ unverified"
            lines.append(f"### Patch {i} — `{p.get('file', '?')}` lines `{p.get('lines_old', '?')}`  [{badge}, risk={p.get('risk', '?')}]")
            lines.append("")
            lines.append(f"**Rationale:** {p.get('rationale', '')}")
            lines.append(f"**Confidence:** {p.get('confidence', 0):.2f}")
            lines.append("")
            lines.append("```diff")
            lines.append(p.get("diff", "").strip())
            lines.append("```")
            lines.append("")

    if v.rejected:
        lines.append("## Rejected findings (transparency)")
        lines.append("")
        lines.append("These were proposed by a lens but rejected by the adversarial verifier.")
        lines.append("")
        for r in v.rejected:
            lines.append(f"- *{r.get('claim', '?')}* — rejected: {r.get('reason', '?')}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Honest scope")
    lines.append("")
    lines.append(
        f"Black Heron v{BLACK_HERON_VERSION} ships with: 4 lenses (code_quality, governance, drift, blind_spot), "
        "adversarial Opus verifier with severity confidence floors, evidence-presence pre-check, "
        "entry-point full-content loading, versioned rubric, cost + time kill-switches, SARIF output, "
        "code-writing suggest mode, parallel lens execution, and external MCP enrichment "
        "(context7 / sequential-thinking / firecrawl / playwright). "
        "Honest gaps documented in `docs/KNOWN_LIMITATIONS.md`."
    )
    path.write_text("\n".join(lines), encoding="utf-8")
