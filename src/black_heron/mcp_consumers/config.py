"""MCP server config schema + loader.

Each enricher maps to a McpServerSpec — command line + env + timeouts + caps.
Default config lives at `src/black_heron/mcp_consumers/mcp.default.json` and is
auto-loaded if no `--mcp-config` is supplied. User overrides at
`~/.black-heron/mcp.json` are also honored when present.

Versioning: the file declares `mcp_config_version` (semver). Loader rejects
unknown major versions — adding a field requires a minor bump, breaking a
field requires a major bump.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class McpServerSpec(BaseModel):
    """One MCP server's spawn config."""

    model_config = ConfigDict(extra="ignore")

    name: str
    command: list[str]
    env: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = 60
    enabled_by_default: bool = False
    description: str = ""

    # Per-enricher caps (optional — interpreted by the enricher)
    max_items: int | None = None
    max_bytes_per_item: int | None = None


class McpConfig(BaseModel):
    """Full MCP config bundle."""

    model_config = ConfigDict(extra="ignore")

    mcp_config_version: str = "1.0.0"
    source: str = "bundled-default"
    servers: dict[str, McpServerSpec] = Field(default_factory=dict)


_BUNDLED_DEFAULT_PATH = Path(__file__).parent / "mcp.default.json"
_USER_PATH = Path(os.path.expanduser("~")) / ".black-heron" / "mcp.json"


def load_mcp_config(path: Path | None = None) -> McpConfig:
    """Load MCP config. Precedence: explicit path > ~/.black-heron/mcp.json > bundled default."""
    chosen: Path
    source: str
    if path is not None:
        chosen = path
        source = str(path)
    elif _USER_PATH.is_file():
        chosen = _USER_PATH
        source = str(_USER_PATH)
    else:
        chosen = _BUNDLED_DEFAULT_PATH
        source = "bundled-default"

    data = json.loads(chosen.read_text(encoding="utf-8"))
    cfg = McpConfig(**data)
    if not cfg.mcp_config_version.startswith("1."):
        raise ValueError(
            f"MCP config at {chosen} declares mcp_config_version={cfg.mcp_config_version!r}; "
            f"this Black Heron build supports major version 1.x only"
        )
    cfg.source = source
    return cfg
