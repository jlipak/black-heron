"""External MCP consumers — BH spawns 3rd-party MCP servers (context7, sequential-thinking, firecrawl, playwright) and queries them for audit enrichment.

Each enricher is opt-in via the `--enrich` CLI flag. Defaults to off; backward-compatible.
A missing binary is logged + skipped, never fails the audit.
"""
from __future__ import annotations

from .client import JsonRpcStdioClient, McpClientError, McpInitializeError, McpToolError
from .config import McpConfig, McpServerSpec, load_mcp_config
from .context7 import Context7Enricher
from .firecrawl import FirecrawlEnricher
from .playwright import PlaywrightEnricher
from .sequential import SequentialThinkingEnricher

ALL_ENRICHERS = {
    "context7": Context7Enricher,
    "sequential-thinking": SequentialThinkingEnricher,
    "firecrawl": FirecrawlEnricher,
    "playwright": PlaywrightEnricher,
}

__all__ = [
    "ALL_ENRICHERS",
    "JsonRpcStdioClient",
    "McpClientError",
    "McpInitializeError",
    "McpToolError",
    "McpConfig",
    "McpServerSpec",
    "load_mcp_config",
    "Context7Enricher",
    "SequentialThinkingEnricher",
    "FirecrawlEnricher",
    "PlaywrightEnricher",
]
