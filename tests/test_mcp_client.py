"""Tests for the generic JSON-RPC stdio MCP client.

We run a real subprocess against the bundled fake_mcp_server.py to exercise
spawn, initialize handshake, tools/list, tools/call, error path, and clean
shutdown — without depending on any third-party MCP package.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from black_heron.mcp_consumers.client import (
    JsonRpcStdioClient,
    McpInitializeError,
    McpToolError,
)

FAKE = Path(__file__).parent / "fixtures" / "fake_mcp_server.py"
CMD = [sys.executable, str(FAKE)]


def test_initialize_and_tools_list() -> None:
    with JsonRpcStdioClient(CMD, timeout_seconds=10) as cli:
        info = cli.initialize()
        assert info.get("protocolVersion") == "2024-11-05"
        tools = cli.list_tools()
        names = [t["name"] for t in tools]
        assert "echo_tool" in names
        assert "error_tool" in names


def test_call_tool_echo_round_trip() -> None:
    with JsonRpcStdioClient(CMD, timeout_seconds=10) as cli:
        cli.initialize()
        result = cli.call_tool("echo_tool", {"hello": "world"})
        text = cli.content_text(result)
        assert "hello" in text and "world" in text


def test_call_tool_error_path_raises() -> None:
    with JsonRpcStdioClient(CMD, timeout_seconds=10) as cli:
        cli.initialize()
        with pytest.raises(McpToolError) as exc:
            cli.call_tool("error_tool")
        assert "intentional failure" in str(exc.value)


def test_missing_binary_raises_initialize_error() -> None:
    with pytest.raises(McpInitializeError):
        with JsonRpcStdioClient(["this-binary-does-not-exist-bh-test"], timeout_seconds=5):
            pass


def test_tools_list_cached() -> None:
    with JsonRpcStdioClient(CMD, timeout_seconds=10) as cli:
        cli.initialize()
        a = cli.list_tools()
        b = cli.list_tools()
        assert a is b  # same object — cached
