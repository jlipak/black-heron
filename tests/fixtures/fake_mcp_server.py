"""Minimal stdio MCP server used by tests.

Implements just enough of the protocol to verify Black Heron's client:
- initialize -> capabilities
- tools/list -> three test tools
- tools/call -> echo the args back as content text
- echo_tool tool always succeeds; error_tool returns a JSON-RPC error.

Run as: python tests/fixtures/fake_mcp_server.py
"""
from __future__ import annotations

import json
import sys

TOOLS = [
    {"name": "echo_tool", "description": "Echo args back as text", "inputSchema": {"type": "object"}},
    {"name": "error_tool", "description": "Always returns an MCP error", "inputSchema": {"type": "object"}},
    {
        "name": "resolve-library-id",
        "description": "Fake context7-style resolver",
        "inputSchema": {"type": "object"},
    },
    {
        "name": "query-docs",
        "description": "Fake context7-style doc fetcher",
        "inputSchema": {"type": "object"},
    },
]


def respond(req_id, result=None, error=None) -> None:
    payload = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def handle(req: dict) -> None:
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}
    if method == "initialize":
        respond(
            req_id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-mcp", "version": "0.0.1"},
            },
        )
    elif method == "tools/list":
        respond(req_id, result={"tools": TOOLS})
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "error_tool":
            respond(req_id, error={"code": -32000, "message": "intentional failure"})
            return
        if name == "resolve-library-id":
            lib = args.get("libraryName") or "unknown"
            respond(
                req_id,
                result={
                    "content": [
                        {"type": "text", "text": json.dumps({"libraryID": f"fake/{lib}"})}
                    ]
                },
            )
            return
        if name == "query-docs":
            lib_id = args.get("context7CompatibleLibraryID") or "unknown"
            respond(
                req_id,
                result={
                    "content": [
                        {"type": "text", "text": f"# Fake docs for {lib_id}\n\nLorem ipsum."}
                    ]
                },
            )
            return
        # default: echo
        respond(
            req_id,
            result={
                "content": [
                    {"type": "text", "text": json.dumps({"tool": name, "args": args})}
                ]
            },
        )
    elif method == "notifications/initialized":
        # no response per MCP spec
        return
    else:
        if req_id is not None:
            respond(req_id, error={"code": -32601, "message": f"Method not found: {method}"})


def main() -> int:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        handle(req)
    return 0


if __name__ == "__main__":
    sys.exit(main())
