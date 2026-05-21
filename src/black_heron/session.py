"""Session persistence for Black Heron.

Each audit run writes a session record to ~/.black-heron/sessions/<timestamp>.json.
Running calibration.json tracks aggregate metrics across all runs (FP rate, cost
average, audit count).

Used by:
- mcp_server.py (post-audit hook)
- cli.py (post-audit hook, optional)
- scripts/self-audit.sh (read calibration.json for historical context)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATE_DIR = Path(os.environ.get("BH_STATE_DIR") or str(Path.home() / ".black-heron"))
CALIBRATION_SCHEMA_VERSION = "1.0.0"


@dataclass
class SessionRecord:
    """One BH audit run, persisted to ~/.black-heron/sessions/<ts>.json."""
    session_id: str
    started_at_utc: str
    ended_at_utc: str
    repo_path: str
    lenses_run: list[str]
    raw_finding_counts: dict[str, int]
    verified_count: int
    rejected_count: int
    total_cost_usd: float
    wall_seconds: float
    rubric_version: str
    bh_version: str = "1.1.0"
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0.0",
            "session_id": self.session_id,
            "started_at_utc": self.started_at_utc,
            "ended_at_utc": self.ended_at_utc,
            "repo_path": self.repo_path,
            "lenses_run": self.lenses_run,
            "raw_finding_counts": self.raw_finding_counts,
            "verified_count": self.verified_count,
            "rejected_count": self.rejected_count,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "wall_seconds": round(self.wall_seconds, 2),
            "rubric_version": self.rubric_version,
            "bh_version": self.bh_version,
            "notes": self.notes,
        }


def ensure_state_dir(state_dir: Path = DEFAULT_STATE_DIR) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "sessions").mkdir(parents=True, exist_ok=True)
    (state_dir / "audits").mkdir(parents=True, exist_ok=True)
    return state_dir


def write_session(record: SessionRecord, state_dir: Path = DEFAULT_STATE_DIR) -> Path:
    """Persist a session record. Returns the file path written."""
    sd = ensure_state_dir(state_dir)
    safe_id = record.session_id.replace(":", "-").replace(" ", "_")
    path = sd / "sessions" / f"{safe_id}.json"
    path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
    update_calibration(record, sd)
    return path


def update_calibration(record: SessionRecord, state_dir: Path = DEFAULT_STATE_DIR) -> Path:
    """Update the running calibration.json with this session's metrics.

    Calibration tracks: total audits run, total cost spent, average wall time,
    per-lens average finding counts, verifier reject ratio average.
    """
    cal_path = state_dir / "calibration.json"
    if cal_path.exists():
        cal = json.loads(cal_path.read_text(encoding="utf-8"))
    else:
        cal = {
            "schema_version": CALIBRATION_SCHEMA_VERSION,
            "first_run_utc": record.started_at_utc,
            "total_audits_run": 0,
            "total_cost_usd": 0.0,
            "total_wall_seconds": 0.0,
            "per_lens_total_findings": {},
            "verified_total": 0,
            "rejected_total": 0,
        }

    cal["total_audits_run"] = cal.get("total_audits_run", 0) + 1
    cal["total_cost_usd"] = round(cal.get("total_cost_usd", 0.0) + record.total_cost_usd, 4)
    cal["total_wall_seconds"] = round(cal.get("total_wall_seconds", 0.0) + record.wall_seconds, 2)
    cal["verified_total"] = cal.get("verified_total", 0) + record.verified_count
    cal["rejected_total"] = cal.get("rejected_total", 0) + record.rejected_count

    pl = cal.setdefault("per_lens_total_findings", {})
    for lens_name, count in record.raw_finding_counts.items():
        pl[lens_name] = pl.get(lens_name, 0) + count

    cal["average_cost_usd"] = round(cal["total_cost_usd"] / cal["total_audits_run"], 4)
    cal["average_wall_seconds"] = round(cal["total_wall_seconds"] / cal["total_audits_run"], 2)
    cal["per_lens_average_findings"] = {
        k: round(v / cal["total_audits_run"], 2) for k, v in pl.items()
    }
    total_decided = cal["verified_total"] + cal["rejected_total"]
    cal["verifier_reject_ratio_average"] = (
        round(cal["rejected_total"] / total_decided, 4) if total_decided else 0.0
    )
    cal["last_updated_utc"] = record.ended_at_utc

    cal_path.write_text(json.dumps(cal, indent=2), encoding="utf-8")
    return cal_path


def session_id_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
