"""Shared helpers across lenses — prompt assembly + JSON-output parsing."""
from __future__ import annotations

import json

from .._models import Finding, RepoContext


def build_repo_prompt(ctx: RepoContext, *, max_files_listed: int = 200) -> str:
    """Render the repo context into a stable prompt block.

    Layout:
      1. Repo header (counts, language, TODO marker count)
      2. Full file listing (up to max_files_listed)
      3. Entry-point files (full content, up to 10KB each — load-bearing)
      4. Recent git history (last 30 commits)
      5. Source samples (4KB-capped small files for coverage)
    """
    parts = [
        "# Repository under audit",
        f"Path: {ctx.path}",
        f"Source/text file count: {ctx.file_count}",
        f"Primary language: {ctx.primary_language}",
        f"TODO/FIXME/XXX/HACK markers across source files: {ctx.todo_count}",
        "",
        "## File listing (authoritative — if a file is not here, it is not in the repo)",
        "\n".join(f"- {p}" for p in ctx.file_listing[:max_files_listed]),
    ]
    if len(ctx.file_listing) > max_files_listed:
        parts.append(f"... and {len(ctx.file_listing) - max_files_listed} more files not listed above.")

    if ctx.entry_points:
        parts.append("")
        parts.append("## Entry-point files (loaded with full content — these are load-bearing for cross-file reasoning)")
        for ep in ctx.entry_points:
            trunc_note = "\n[Content truncated at 10KB — file is larger than that]" if ep.truncated else ""
            parts.append(f"\n### {ep.path}  (role: {ep.role}){trunc_note}\n```\n{ep.content}\n```")

    parts.append("")
    parts.append("## Recent git history (last 30 commits)")
    if ctx.git_log_recent:
        parts.extend(f"- {c}" for c in ctx.git_log_recent)
    else:
        parts.append("(no git history available)")

    parts.append("")
    parts.append("## Source samples (small files only, 4KB cap each — coverage, not load-bearing)")
    for path, content in ctx.sample_files.items():
        parts.append(f"\n### {path}\n```\n{content}\n```")

    if getattr(ctx, "external_enrichments", None):
        parts.append("")
        parts.append("---")
        parts.append("# External MCP enrichments")
        parts.append("")
        parts.append(
            "The blocks below come from external MCP servers (context7, firecrawl, playwright, "
            "sequential-thinking) and are advisory context. Treat them like documentation, NOT "
            "like in-repo evidence: a finding's `evidence` field must still be a verbatim "
            "substring of an in-repo file unless the finding explicitly cites an enrichment "
            "block and the claim is about that external resource itself."
        )
        for name, payload in ctx.external_enrichments.items():
            parts.append("")
            parts.append(payload)

    return "\n".join(parts)


def parse_findings(text: str, lens: str) -> list[Finding]:
    """Robust JSON extraction — finds first {...} block, parses, validates.

    Parse failures and validation failures are logged to stderr so silent
    drops are observable (Apollo lesson: silent failure is the most expensive
    failure). Bad findings are skipped, not raised, to preserve audit progress.
    """
    import sys
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        sys.stderr.write(f"[bh:{lens}] no JSON block in lens output (len={len(text)})\n")
        return []
    payload = text[start:end + 1]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[bh:{lens}] JSON decode error: {e}\n")
        return []

    out: list[Finding] = []
    skipped = 0
    for raw in data.get("findings", []):
        raw.setdefault("lens", lens)
        try:
            out.append(Finding(**raw))
        except Exception as e:
            skipped += 1
            sys.stderr.write(f"[bh:{lens}] finding validation skipped: {type(e).__name__}: {str(e)[:120]}\n")
            continue
    if skipped:
        sys.stderr.write(f"[bh:{lens}] {skipped} finding(s) skipped due to validation errors\n")
    return out
