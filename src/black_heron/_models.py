"""Pydantic schemas for Findings, RepoContext, EntryPoint, Rubric."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lens: str
    severity: Literal["P0", "P1", "P2"]
    file: str
    lines: str
    claim: str
    evidence: str
    why_it_matters: str
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty_reason: str | None = None  # required by prompt when confidence < 0.6
    absence_claim: bool = False  # set when finding asserts a file/feature is missing


class EntryPoint(BaseModel):
    """Source file that should be loaded with full content (not 4KB-capped sample)."""
    path: str
    role: Literal[
        "package_manifest",
        "language_config",
        "build_config",
        "module_init",
        "cli_entry",
        "server_entry",
        "rubric_or_policy",
    ]
    content: str  # capped at ENTRY_POINT_BYTE_CAP in discovery
    truncated: bool = False


class RepoContext(BaseModel):
    path: str
    file_count: int
    primary_language: str
    file_listing: list[str]
    sample_files: dict[str, str]
    entry_points: list[EntryPoint] = []
    git_log_recent: list[str]
    todo_count: int
    external_enrichments: dict[str, str] = Field(default_factory=dict)


class SuggestedPatch(BaseModel):
    """A patch proposed by code_writer for a verified P0/P1 finding.

    NEVER auto-applied in v1.2 — suggest mode only. User reviews + applies manually.
    """
    model_config = ConfigDict(extra="ignore")

    file: str
    lines_old: str  # "L42-L48" or "L42"
    diff: str       # unified-diff format string
    rationale: str  # 1-2 sentence why this patch addresses the finding
    confidence: float = Field(ge=0.0, le=1.0)
    risk: Literal["low", "medium", "high"]  # blast radius assessment
    verifier_approved: bool = False  # set true after verifier sanity-check


class Rubric(BaseModel):
    """Versioned audit policy. Loaded from rubric.default.json or user-supplied path."""
    model_config = ConfigDict(extra="ignore")

    rubric_version: str
    schema_version: str = "1.0.0"
    source: str = "bundled-default"

    severity_confidence_floors: dict[Literal["P0", "P1", "P2"], float] = Field(
        default_factory=lambda: {"P0": 0.85, "P1": 0.70, "P2": 0.50}
    )
    severity_max_per_run: dict[Literal["P0", "P1", "P2"], int] = Field(
        default_factory=lambda: {"P0": 10, "P1": 25, "P2": 50}
    )
    kill_switch_total_findings_cap: int = 50

    lens_enabled: dict[str, bool] = Field(
        default_factory=lambda: {
            "code_quality": True,
            "governance": True,
            "drift": True,
            "blind_spot": True,
        }
    )

    cost_cap_usd: float = 2.0
    time_cap_seconds: int = 300

    ignore_patterns: list[str] = Field(
        default_factory=lambda: [
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "dist", "build", ".pytest_cache", ".mypy_cache", ".ruff_cache",
            ".idea", ".vscode", "audit_output", "coverage",
        ]
    )
