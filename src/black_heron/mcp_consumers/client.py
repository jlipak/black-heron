"""Generic JSON-RPC stdio MCP client.

Spawns an MCP server as a subprocess, performs the initialize handshake,
exposes call_tool() over JSON-RPC 2.0. Sync-blocking with a reader thread
on stdout to match Black Heron's existing non-async architecture.

Failure modes are explicit:
- McpInitializeError    — handshake failed or binary not found
- McpToolError          — tool returned an MCP error or call timed out
- McpClientError        — parent class

Callers must use the context-manager form so subprocess and reader thread
are always cleaned up:

    with JsonRpcStdioClient(["npx", "-y", "@some/mcp"], timeout=30) as cli:
        cli.initialize()
        tools = cli.list_tools()
        out = cli.call_tool("scrape", {"url": "https://example.com"})
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "black-heron-consumer"
CLIENT_VERSION = "1.3.0"


class McpClientError(Exception):
    """Base class for MCP client errors."""


class McpInitializeError(McpClientError):
    """Raised when the MCP handshake fails or binary is missing."""


class McpToolError(McpClientError):
    """Raised when a tool call returns an error or times out."""


class JsonRpcStdioClient:
    """Synchronous JSON-RPC 2.0 client over a subprocess stdio MCP server."""

    def __init__(
        self,
        command: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int = 60,
        log_stderr: bool = True,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.env = env
        self.timeout_seconds = timeout_seconds
        self.log_stderr = log_stderr

        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._responses: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._next_id = 0
        self._initialized = False
        self._tools_cache: list[dict] | None = None

    # ----- lifecycle ---------------------------------------------------------

    def __enter__(self) -> JsonRpcStdioClient:
        self._spawn()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _spawn(self) -> None:
        binary = self.command[0]
        if shutil.which(binary) is None and not os.path.isabs(binary):
            raise McpInitializeError(
                f"MCP server binary not found on PATH: {binary!r}. "
                f"Install the server or adjust --mcp-config."
            )
        full_env = os.environ.copy()
        if self.env:
            full_env.update(self.env)
        try:
            self._proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd,
                env=full_env,
                text=True,
                bufsize=1,
                encoding="utf-8",
            )
        except (OSError, FileNotFoundError) as e:
            raise McpInitializeError(f"Failed to spawn {self.command!r}: {e}") from e

        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        self._stderr_reader = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_reader.start()

    def close(self) -> None:
        self._stop.set()
        if self._proc is None:
            return
        try:
            if self._proc.stdin and not self._proc.stdin.closed:
                self._proc.stdin.close()
        except (OSError, BrokenPipeError):
            pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            try:
                self._proc.kill()
            except OSError:
                pass
        self._proc = None

    # ----- IO threads --------------------------------------------------------

    def _read_stdout(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for raw in self._proc.stdout:
            if self._stop.is_set():
                return
            line = raw.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._responses.put(msg)

    def _drain_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        for raw in self._proc.stderr:
            if self._stop.is_set():
                return
            if self.log_stderr:
                sys.stderr.write(f"[mcp-stderr] {raw.rstrip()}\n")

    # ----- request/response --------------------------------------------------

    def _alloc_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _send(self, payload: dict) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise McpClientError("Client not started")
        line = json.dumps(payload) + "\n"
        try:
            self._proc.stdin.write(line)
            self._proc.stdin.flush()
        except (OSError, BrokenPipeError) as e:
            raise McpClientError(f"Failed to write to MCP server stdin: {e}") from e

    def _request(self, method: str, params: dict | None = None) -> dict:
        req_id = self._alloc_id()
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)
        return self._await_response(req_id)

    def _notify(self, method: str, params: dict | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)

    def _await_response(self, req_id: int) -> dict:
        deadline = time.time() + self.timeout_seconds
        leftover: list[dict] = []
        try:
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise McpToolError(
                        f"Timeout waiting for response to id={req_id} after {self.timeout_seconds}s"
                    )
                try:
                    msg = self._responses.get(timeout=min(remaining, 1.0))
                except queue.Empty:
                    if self._proc is not None and self._proc.poll() is not None:
                        raise McpClientError(
                            f"MCP server exited (rc={self._proc.returncode}) "
                            f"while waiting for response to id={req_id}"
                        )
                    continue
                if msg.get("id") != req_id:
                    leftover.append(msg)
                    continue
                if "error" in msg:
                    err = msg["error"]
                    raise McpToolError(
                        f"MCP error code={err.get('code')} message={err.get('message')}"
                    )
                return msg.get("result") or {}
        finally:
            for m in leftover:
                self._responses.put(m)

    # ----- MCP protocol surface ---------------------------------------------

    def initialize(self) -> dict:
        if self._initialized:
            return {}
        result = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
        )
        self._notify("notifications/initialized")
        self._initialized = True
        return result

    def list_tools(self) -> list[dict]:
        if self._tools_cache is not None:
            return self._tools_cache
        if not self._initialized:
            self.initialize()
        result = self._request("tools/list")
        tools = result.get("tools") or []
        self._tools_cache = tools
        return tools

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        if not self._initialized:
            self.initialize()
        return self._request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )

    def content_text(self, result: dict) -> str:
        """Extract concatenated text from an MCP tools/call result."""
        out: list[str] = []
        for chunk in result.get("content", []):
            if isinstance(chunk, dict) and chunk.get("type") == "text":
                txt = chunk.get("text")
                if isinstance(txt, str):
                    out.append(txt)
        return "\n".join(out).strip()
