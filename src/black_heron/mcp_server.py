"""Black Heron stdio MCP server.

Exposes 3 tools to MCP clients (e.g., Claude Code):
- audit_repository(repo_path, lenses?, cost_cap?, time_cap?, out_dir?)
- verify_findings(findings_json_path) — verifier-only mode on external tool output
- quick_scan(repo_path) — single-lens fast scan (code_quality only)

Protocol: JSON-RPC 2.0 over stdin/stdout per MCP spec.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from ._models import Finding, Rubric
from .cost_tracker import CostTracker
from .discovery import build_context
from .lenses import ALL_LENSES, run_blind_spot
from .report import write_report
from .rubric import load_rubric
from .synthesis import synthesize, VerifierResult

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "black-heron"
SERVER_VERSION = "1.3.1"


TOOLS_DESCRIPTOR = [
    {
        "name": "audit_repository",
        "description": "Run a full Black Heron audit on a local repository. 4 lenses (code_quality, governance, drift, blind_spot) + adversarial Opus verifier. Returns summary metrics; full report at out_dir.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Absolute path to the repository to audit"},
                "lenses": {"type": "string", "description": "Comma-separated lens names. Default: all four."},
                "cost_cap_usd": {"type": "number", "description": "Override rubric cost cap (default $2.00)."},
                "time_cap_seconds": {"type": "integer", "description": "Override rubric time cap (default 300s)."},
                "out_dir": {"type": "string", "description": "Output directory for REPORT.md, findings.json, findings.sarif. Default: <repo_path>/.bh-audit/"},
            },
            "required": ["repo_path"],
        },
    },
    {
        "name": "verify_findings",
        "description": "Run the adversarial verifier (Opus 4.7) on findings produced by another tool. Accepts a JSON file with a 'findings' array matching the Black Heron Finding schema. Returns kept/rejected partition.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "findings_json_path": {"type": "string", "description": "Path to JSON file with findings array"},
                "repo_path": {"type": "string", "description": "Path to the repository being audited (for context)"},
            },
            "required": ["findings_json_path", "repo_path"],
        },
    },
    {
        "name": "quick_scan",
        "description": "Fast single-lens scan (code_quality only, no verifier). Cheaper and faster than full audit. Use for routine pre-commit checks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Absolute path to the repository to scan"},
            },
            "required": ["repo_path"],
        },
    },
]


def _send(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _log(msg: str) -> None:
    sys.stderr.write(f"[bh-mcp] {msg}\n")
    sys.stderr.flush()


def _response(req_id, result=None, error=None) -> dict:
    payload = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return payload


def handle_initialize(params: dict) -> dict:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
    }


def handle_tools_list() -> dict:
    return {"tools": TOOLS_DESCRIPTOR}


def _ensure_api_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        load_dotenv(override=False)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not in environment")


def tool_audit_repository(args: dict) -> dict:
    _ensure_api_key()
    repo_path = Path(args["repo_path"]).resolve()
    if not repo_path.is_dir():
        raise FileNotFoundError(f"Not a directory: {repo_path}")
    out_dir = Path(args.get("out_dir") or (repo_path / ".bh-audit"))
    lens_csv = args.get("lenses") or "code_quality,governance,drift,blind_spot"
    lens_list = [n.strip() for n in lens_csv.split(",") if n.strip()]

    rubric = load_rubric(None)
    if args.get("cost_cap_usd") is not None:
        rubric.cost_cap_usd = float(args["cost_cap_usd"])
    if args.get("time_cap_seconds") is not None:
        rubric.time_cap_seconds = int(args["time_cap_seconds"])

    tracker = CostTracker(cost_cap_usd=rubric.cost_cap_usd)
    ctx = build_context(repo_path, extra_ignores=rubric.ignore_patterns)
    client = anthropic.Anthropic()

    all_findings: list[Finding] = []
    raw_counts: dict[str, int] = {}
    first_pass = [n for n in lens_list if n != "blind_spot"]
    for name in first_pass:
        if tracker.exceeded():
            break
        findings = ALL_LENSES[name](ctx, client, tracker)
        raw_counts[name] = len(findings)
        all_findings.extend(findings)
    if "blind_spot" in lens_list and not tracker.exceeded():
        findings = run_blind_spot(ctx, all_findings, client, tracker)
        raw_counts["blind_spot"] = len(findings)
        all_findings.extend(findings)

    verifier = synthesize(ctx, all_findings, client, tracker, rubric)
    metrics = {
        "total_cost_usd": round(tracker.cost_so_far, 4),
        "per_lens_cost_usd": {k: round(v, 4) for k, v in tracker.lens_cost.items()},
        "raw_finding_counts": raw_counts,
        "rubric_version": rubric.rubric_version,
        "rubric_source": rubric.source,
    }
    write_report(out_dir, ctx, verifier, raw_counts, metrics)

    return {
        "content": [{
            "type": "text",
            "text": (
                f"Black Heron audit complete on {repo_path.name}.\n"
                f"Lenses: {', '.join(lens_list)}\n"
                f"Raw findings: {sum(raw_counts.values())}; Verified: {len(verifier.verified)}; Rejected: {len(verifier.rejected)}\n"
                f"Cost: ${tracker.cost_so_far:.3f}\n"
                f"Reports written to: {out_dir}\n"
            ),
        }],
    }


def tool_verify_findings(args: dict) -> dict:
    _ensure_api_key()
    findings_path = Path(args["findings_json_path"]).resolve()
    repo_path = Path(args["repo_path"]).resolve()
    data = json.loads(findings_path.read_text(encoding="utf-8"))
    raw = data.get("findings", data) if isinstance(data, dict) else data
    findings = []
    for f in raw:
        try:
            findings.append(Finding(**f))
        except Exception:
            continue

    rubric = load_rubric(None)
    tracker = CostTracker(cost_cap_usd=rubric.cost_cap_usd)
    ctx = build_context(repo_path, extra_ignores=rubric.ignore_patterns)
    client = anthropic.Anthropic()
    verifier = synthesize(ctx, findings, client, tracker, rubric)
    return {
        "content": [{
            "type": "text",
            "text": (
                f"Verifier processed {len(findings)} findings.\n"
                f"Kept: {len(verifier.verified)}; Rejected: {len(verifier.rejected)}\n"
                f"Cost: ${tracker.cost_so_far:.3f}\n"
                f"\nVerified findings:\n"
                + "\n".join(f"- [{f.get('severity')}] {f.get('file')}: {f.get('claim')}" for f in verifier.verified[:20])
            ),
        }],
    }


def tool_quick_scan(args: dict) -> dict:
    _ensure_api_key()
    repo_path = Path(args["repo_path"]).resolve()
    rubric = load_rubric(None)
    rubric.cost_cap_usd = 0.50  # quick scan budget
    tracker = CostTracker(cost_cap_usd=rubric.cost_cap_usd)
    ctx = build_context(repo_path, extra_ignores=rubric.ignore_patterns)
    client = anthropic.Anthropic()
    findings = ALL_LENSES["code_quality"](ctx, client, tracker)
    summary = (
        f"Quick scan (code_quality lens only) on {repo_path.name}: "
        f"{len(findings)} findings, ${tracker.cost_so_far:.3f}.\n\n"
        + "\n".join(f"- [{f.severity}] {f.file} {f.lines}: {f.claim}" for f in findings[:10])
    )
    return {"content": [{"type": "text", "text": summary}]}


TOOL_HANDLERS = {
    "audit_repository": tool_audit_repository,
    "verify_findings": tool_verify_findings,
    "quick_scan": tool_quick_scan,
}


def handle_tools_call(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown tool: {name}")
    return handler(args)


def main() -> int:
    _log(f"Black Heron MCP server v{SERVER_VERSION} starting on stdio")
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _log(f"JSON decode error: {e}")
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        try:
            if method == "initialize":
                _send(_response(req_id, result=handle_initialize(params)))
            elif method == "tools/list":
                _send(_response(req_id, result=handle_tools_list()))
            elif method == "tools/call":
                _send(_response(req_id, result=handle_tools_call(params)))
            elif method == "notifications/initialized":
                # acknowledgment; no response per MCP spec for notifications
                pass
            else:
                _send(_response(req_id, error={"code": -32601, "message": f"Method not found: {method}"}))
        except Exception as e:
            _log(f"Tool error: {e}\n{traceback.format_exc()}")
            _send(_response(req_id, error={"code": -32000, "message": str(e)}))

    _log("Server stopped (stdin closed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
