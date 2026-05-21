"""Base protocol + dataclasses shared across enrichers."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Protocol

from .._models import RepoContext
from .client import JsonRpcStdioClient, McpClientError, McpInitializeError
from .config import McpServerSpec


@dataclass
class EnrichmentReport:
    """One enricher's per-run report — metrics + payload for the prompt."""

    name: str
    available: bool
    items_fetched: int = 0
    bytes_fetched: int = 0
    wall_seconds: float = 0.0
    skipped_reason: str | None = None  # e.g. "binary not found", "no inputs to enrich"
    payload_markdown: str = ""
    queries: list[str] = field(default_factory=list)

    def as_metric(self) -> dict:
        return {
            "name": self.name,
            "available": self.available,
            "items_fetched": self.items_fetched,
            "bytes_fetched": self.bytes_fetched,
            "wall_seconds": round(self.wall_seconds, 2),
            "skipped_reason": self.skipped_reason,
            "queries": self.queries,
        }


class Enricher(Protocol):
    """One pluggable external-MCP enricher."""

    name: str

    def __init__(self, spec: McpServerSpec) -> None: ...
    def run(self, ctx: RepoContext) -> EnrichmentReport: ...


class BaseEnricher:
    """Common implementation hooks for enrichers."""

    name: str = "base"

    def __init__(self, spec: McpServerSpec) -> None:
        self.spec = spec

    def _open_client(self) -> JsonRpcStdioClient:
        return JsonRpcStdioClient(
            self.spec.command,
            env=self.spec.env,
            timeout_seconds=self.spec.timeout_seconds,
            log_stderr=False,
        )

    def _log(self, msg: str) -> None:
        sys.stderr.write(f"[bh:{self.name}] {msg}\n")

    def _skip(self, reason: str) -> EnrichmentReport:
        self._log(f"skipped: {reason}")
        return EnrichmentReport(name=self.name, available=False, skipped_reason=reason)

    def _safe_open(self, client: JsonRpcStdioClient) -> bool:
        """Try to initialize; return True on success, False on McpInitializeError."""
        try:
            client.initialize()
            return True
        except McpInitializeError as e:
            self._log(f"initialize failed: {e}")
            return False
        except McpClientError as e:
            self._log(f"client error during initialize: {e}")
            return False
