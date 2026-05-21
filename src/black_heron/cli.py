"""Black Heron CLI entry point."""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from ._models import Rubric
from .code_writer import suggest_patches
from .cost_tracker import CostTracker
from .discovery import build_context
from .enrichment import enrich_context, parse_enrich_flag
from .lenses import ALL_LENSES, run_blind_spot
from .mcp_consumers import ALL_ENRICHERS, load_mcp_config
from .report import write_report
from .rubric import load_rubric
from .session import SessionRecord, session_id_now, utcnow_iso, write_session
from .synthesis import synthesize

console = Console()


@click.command()
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--lenses",
    "lens_arg",
    default="code_quality,governance,drift,blind_spot",
    help="Comma-separated lenses. Default: all four (blind_spot runs last and reads other findings).",
)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("audit"),
    help="Output directory for REPORT.md, findings.json, findings.sarif. Default: ./audit/",
)
@click.option(
    "--env",
    "env_path",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
    default=None,
    help="Path to a .env file containing ANTHROPIC_API_KEY.",
)
@click.option(
    "--rubric",
    "rubric_path",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
    default=None,
    help="Path to a custom rubric.json (default: bundled rubric.default.json).",
)
@click.option("--cost-cap", type=float, default=None, help="Override rubric cost cap (USD).")
@click.option("--time-cap", type=int, default=None, help="Override rubric time cap (seconds).")
@click.option("--dry-run", is_flag=True, help="Print what would be sent; no API calls.")
@click.option(
    "--mode",
    type=click.Choice(["audit", "suggest"]),
    default="audit",
    help="`audit` = lenses+verifier only (default). `suggest` = also draft patches for verified P0/P1 findings.",
)
@click.option(
    "--parallel/--no-parallel",
    default=True,
    help="Run first-pass lenses (code_quality, governance, drift) in parallel via ThreadPoolExecutor. Default: enabled.",
)
@click.option(
    "--enrich",
    "enrich_arg",
    default="none",
    help="External MCP enrichment: 'none' (default), 'all', or comma list (context7,sequential-thinking,firecrawl,playwright). "
         "Each enricher is skipped silently if its binary is not on PATH.",
)
@click.option(
    "--mcp-config",
    "mcp_config_path",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
    default=None,
    help="Path to a custom MCP config JSON. Falls back to ~/.black-heron/mcp.json, then bundled default.",
)
def audit(
    repo_path: Path,
    lens_arg: str,
    out_dir: Path,
    env_path: Path | None,
    rubric_path: Path | None,
    cost_cap: float | None,
    time_cap: int | None,
    dry_run: bool,
    mode: str,
    parallel: bool,
    enrich_arg: str,
    mcp_config_path: Path | None,
) -> None:
    """Run a Black Heron audit on REPO_PATH and write reports to --out."""
    if env_path is not None:
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)

    rubric = load_rubric(rubric_path)
    if cost_cap is not None:
        rubric.cost_cap_usd = cost_cap
    if time_cap is not None:
        rubric.time_cap_seconds = time_cap

    if not dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY missing.[/red] Set it in env or pass --env <path>.")
        sys.exit(1)

    lens_list = [name.strip() for name in lens_arg.split(",") if name.strip()]
    unknown = [n for n in lens_list if n not in ALL_LENSES]
    if unknown:
        console.print(f"[red]Unknown lens(es):[/red] {unknown}. Valid: {list(ALL_LENSES)}")
        sys.exit(2)

    enabled_in_rubric = [n for n in lens_list if rubric.lens_enabled.get(n, True)]
    if enabled_in_rubric != lens_list:
        disabled = [n for n in lens_list if n not in enabled_in_rubric]
        console.print(f"[yellow]Rubric disables[/yellow] lens(es): {disabled}")
        lens_list = enabled_in_rubric

    console.print(Panel.fit(
        f"[bold]Black Heron v1.3[/bold] — multi-lens repository audit\n"
        f"Repo: [cyan]{repo_path}[/cyan]\n"
        f"Lenses: {', '.join(lens_list)}\n"
        f"Enrich: {enrich_arg or 'none'}\n"
        f"Rubric: [magenta]{rubric.rubric_version}[/magenta] | "
        f"Cost cap: ${rubric.cost_cap_usd:.2f} | Time cap: {rubric.time_cap_seconds}s"
        + ("  [yellow](DRY RUN)[/yellow]" if dry_run else ""),
        border_style="white",
    ))

    started_at = time.time()
    tracker = CostTracker(cost_cap_usd=rubric.cost_cap_usd)

    with console.status("[bold]Discovery[/bold] — walking the repo..."):
        ctx = build_context(repo_path, extra_ignores=rubric.ignore_patterns)
    console.print(
        f"  Files: {ctx.file_count} | Lang: {ctx.primary_language} | "
        f"TODOs: {ctx.todo_count} | git commits: {len(ctx.git_log_recent)} | "
        f"entry-points: {len(ctx.entry_points)}"
    )

    try:
        enrich_list = parse_enrich_flag(enrich_arg, list(ALL_ENRICHERS.keys()))
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(2)
    enrichment_reports: list = []
    if enrich_list:
        mcp_config = load_mcp_config(mcp_config_path)
        console.print(
            f"[bold]MCP enrichment[/bold] (source: [magenta]{mcp_config.source}[/magenta]): "
            f"{', '.join(enrich_list)}"
        )
        with console.status("[bold]Enrichment[/bold] — calling external MCP servers..."):
            ctx, enrichment_reports = enrich_context(ctx, enrich_list, mcp_config)
        for rep in enrichment_reports:
            if rep.available and rep.items_fetched:
                console.print(
                    f"  [green]{rep.name}[/green]: "
                    f"{rep.items_fetched} item(s), {rep.bytes_fetched} bytes, "
                    f"{rep.wall_seconds:.1f}s"
                )
            else:
                console.print(
                    f"  [yellow]{rep.name}[/yellow]: skipped — {rep.skipped_reason}"
                )

    if dry_run:
        from .lenses._common import build_repo_prompt
        prompt = build_repo_prompt(ctx)
        console.print(f"\n[yellow]Dry-run prompt size:[/yellow] {len(prompt)} chars")
        console.print(f"Entry-points loaded: {[ep.path for ep in ctx.entry_points]}")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "dry-run-prompt.md").write_text(prompt, encoding="utf-8")
        console.print(f"[green]Wrote dry-run prompt:[/green] {out_dir / 'dry-run-prompt.md'}")
        return

    client = anthropic.Anthropic()

    all_findings = []
    raw_counts: dict[str, int] = {}
    lens_timings: dict[str, float] = {}

    # First three lenses run in parallel (ThreadPoolExecutor) if --parallel; else sequential.
    # blind_spot runs last and depends on prior findings (always sequential, after first-pass joins).
    first_pass = [n for n in lens_list if n != "blind_spot"]

    if parallel and len(first_pass) > 1:
        if tracker.exceeded():
            console.print(f"[red]Cost cap ${rubric.cost_cap_usd:.2f} exceeded[/red] before first-pass; aborting.")
            sys.exit(4)
        console.print(f"[bold]First-pass lenses[/bold] running in parallel: {', '.join(first_pass)}")
        pass_t0 = time.time()
        with ThreadPoolExecutor(max_workers=len(first_pass)) as pool:
            future_to_name = {
                pool.submit(ALL_LENSES[name], ctx, client, tracker): name
                for name in first_pass
            }
            for fut in as_completed(future_to_name):
                name = future_to_name[fut]
                try:
                    findings = fut.result()
                except Exception as e:
                    console.print(f"  [red]{name}[/red] FAILED: {type(e).__name__}: {e}")
                    findings = []
                lens_timings[name] = time.time() - pass_t0  # wall-time bucket per lens
                raw_counts[name] = len(findings)
                all_findings.extend(findings)
                console.print(
                    f"  [green]{name}[/green]: {len(findings)} raw findings  "
                    f"(${tracker.cost_so_far:.3f} cumulative)"
                )
        console.print(f"[dim]First-pass parallel wall time: {time.time() - pass_t0:.1f}s[/dim]")
    else:
        for name in first_pass:
            if tracker.exceeded():
                console.print(f"[red]Cost cap ${rubric.cost_cap_usd:.2f} exceeded[/red] before {name}; aborting.")
                sys.exit(4)
            if time.time() - started_at > rubric.time_cap_seconds:
                console.print(f"[red]Time cap {rubric.time_cap_seconds}s exceeded[/red]; aborting.")
                sys.exit(5)
            t0 = time.time()
            with console.status(f"[bold]{name}[/bold] lens running..."):
                findings = ALL_LENSES[name](ctx, client, tracker)
            lens_timings[name] = time.time() - t0
            raw_counts[name] = len(findings)
            all_findings.extend(findings)
            console.print(
                f"  [green]{name}[/green]: {len(findings)} raw findings  "
                f"({lens_timings[name]:.1f}s, ${tracker.cost_so_far:.3f} cumulative)"
            )

    if "blind_spot" in lens_list:
        if tracker.exceeded() or (time.time() - started_at > rubric.time_cap_seconds):
            console.print("[yellow]Skipping blind_spot lens — cost or time cap reached.[/yellow]")
        else:
            t0 = time.time()
            with console.status("[bold]blind_spot[/bold] lens running (reads other lenses' output)..."):
                findings = run_blind_spot(ctx, all_findings, client, tracker)
            lens_timings["blind_spot"] = time.time() - t0
            raw_counts["blind_spot"] = len(findings)
            all_findings.extend(findings)
            console.print(
                f"  [green]blind_spot[/green]: {len(findings)} raw findings  "
                f"({lens_timings['blind_spot']:.1f}s, ${tracker.cost_so_far:.3f} cumulative)"
            )

    console.print("\n[bold]Adversarial verifier[/bold] (Opus)...")
    try:
        verifier = synthesize(ctx, all_findings, client, tracker, rubric)
    except RuntimeError as e:
        console.print(f"[red]Kill-switch triggered:[/red] {e}")
        sys.exit(3)

    wall_seconds = time.time() - started_at
    console.print(
        f"  Verified: {len(verifier.verified)} | Rejected: {len(verifier.rejected)}  "
        f"(verifier ${tracker.cost_so_far - sum(tracker.lens_cost.get(n, 0.0) for n in raw_counts):.3f})"
    )

    # Suggest-mode: draft patches for high-confidence P0/P1 verified findings
    suggested_patches = []
    if mode == "suggest" and verifier.verified and not tracker.exceeded():
        console.print("\n[bold]Code-writer (suggest mode)[/bold] — drafting patches for P0/P1...")
        patches = suggest_patches(verifier.verified, repo_path, client, tracker)
        suggested_patches = [p.model_dump() for p in patches]
        approved = sum(1 for p in patches if p.verifier_approved)
        console.print(
            f"  Patches drafted: {len(patches)} | Verifier-approved: {approved}"
        )
    console.print(
        f"\n[bold]Totals:[/bold] wall {wall_seconds:.1f}s, cost ${tracker.cost_so_far:.3f}"
    )

    metrics = {
        "wall_seconds": round(wall_seconds, 2),
        "total_cost_usd": round(tracker.cost_so_far, 4),
        "per_lens_cost_usd": {k: round(v, 4) for k, v in tracker.lens_cost.items()},
        "per_lens_seconds": {k: round(v, 2) for k, v in lens_timings.items()},
        "raw_finding_counts": raw_counts,
        "rubric_version": rubric.rubric_version,
        "rubric_source": rubric.source,
        "mode": mode,
        "suggested_patches_count": len(suggested_patches),
        "enrichment": [r.as_metric() for r in enrichment_reports],
    }
    write_report(out_dir, ctx, verifier, raw_counts, metrics, suggested_patches)
    console.print(
        f"\n[bold green]Reports written:[/bold green] "
        f"{out_dir / 'REPORT.md'} | {out_dir / 'findings.json'} | {out_dir / 'findings.sarif'}"
    )

    # Persist session record to ~/.black-heron/sessions/ + update calibration.json
    sid = session_id_now()
    record = SessionRecord(
        session_id=sid,
        started_at_utc=datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat(),
        ended_at_utc=utcnow_iso(),
        repo_path=str(repo_path),
        lenses_run=lens_list,
        raw_finding_counts=raw_counts,
        verified_count=len(verifier.verified),
        rejected_count=len(verifier.rejected),
        total_cost_usd=tracker.cost_so_far,
        wall_seconds=wall_seconds,
        rubric_version=rubric.rubric_version,
    )
    try:
        session_path = write_session(record)
        console.print(f"[dim]Session record: {session_path}[/dim]")
    except OSError as e:
        console.print(f"[yellow]Session record write failed: {e}[/yellow]")


if __name__ == "__main__":
    audit()
