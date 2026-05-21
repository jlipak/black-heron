"""Render the verified findings into Markdown + JSON + SARIF."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ._models import RepoContext
from .synthesis import VerifierResult

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
SARIF_LEVEL = {"P0": "error", "P1": "warning", "P2": "note"}
BLACK_HERON_VERSION = "1.0.0"


def write_report(
    out_dir: Path,
    ctx: RepoContext,
    verifier: VerifierResult,
    lens_raw_counts: dict[str, int],
    metrics: dict | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = metrics or {}
    _write_findings_json(out_dir / "findings.json", ctx, verifier, lens_raw_counts, metrics)
    _write_findings_sarif(out_dir / "findings.sarif", ctx, verifier)
    _write_report_md(out_dir / "REPORT.md", ctx, verifier, lens_raw_counts, metrics)


def _write_findings_json(
    path: Path,
    ctx: RepoContext,
    v: VerifierResult,
    raw: dict,
    metrics: dict,
) -> None:
    payload = {
        "schema_version": "1.0.0",
        "black_heron_version": BLACK_HERON_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
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
                    "informationUri": "https://github.com/lipakjosip442-png/black-heron",
                    "rules": list(rules_seen.values()),
                }
            },
            "results": results,
            "originalUriBaseIds": {"%SRCROOT%": {"uri": Path(ctx.path).as_uri() + "/"}},
        }],
    }
    path.write_text(json.dumps(sarif, indent=2), encoding="utf-8")


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
) -> None:
    by_sev: dict[str, list[dict]] = {"P0": [], "P1": [], "P2": []}
    for f in v.verified:
        sev = f.get("severity", "P2")
        by_sev.setdefault(sev, []).append(f)
    p0, p1, p2 = len(by_sev["P0"]), len(by_sev["P1"]), len(by_sev["P2"])

    lines: list[str] = []
    lines.append("# Black Heron — Audit Report")
    lines.append("")
    lines.append(f"> Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by Black Heron v{BLACK_HERON_VERSION}")
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
                lines.append(f"**Evidence:**")
                lines.append("```")
                lines.append(f.get("evidence", "").strip())
                lines.append("```")
                lines.append(f"**Why it matters:** {f.get('why_it_matters', '')}")
                if f.get("verifier_note"):
                    lines.append(f"**Verifier note:** {f.get('verifier_note')}")
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
    lines.append("## Honest scope (v1.0)")
    lines.append("")
    lines.append("Black Heron v1.0 ships with: 4 lenses (code_quality, governance, drift, blind_spot), adversarial Opus verifier with severity confidence floors, evidence-presence pre-check, entry-point full-content loading, versioned rubric, cost + time kill-switches, SARIF output. Honest gaps documented in `KNOWN_LIMITATIONS.md`. See `README.md` for v1.1 roadmap.")
    path.write_text("\n".join(lines), encoding="utf-8")
