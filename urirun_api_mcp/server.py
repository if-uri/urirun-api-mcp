from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "urirun-connector-mcp", "version": "0.2.0"}


def runtime_url() -> str:
    return (os.environ.get("URIRUN_RUNTIME_URL") or "http://127.0.0.1:8765").rstrip("/")


def llm_api_base() -> str:
    return (
        os.environ.get("URIRUN_LLM_API_BASE")
        or os.environ.get("OPENAI_API_BASE")
        or os.environ.get("OPENROUTER_BASE_URL")
        or "https://llm.urirun.com/api/v1"
    ).rstrip("/")


def fetch_routes() -> list[dict[str, Any]]:
    for path in ("/routes", "/api/routes"):
        try:
            resp = requests.get(runtime_url() + path, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            routes = data.get("routes", data)
            if isinstance(routes, dict):
                routes = list(routes.values())
            if isinstance(routes, list):
                return [r for r in routes if isinstance(r, dict) and r.get("uri")]
        except Exception:
            continue
    return []


def tool_name(uri: str) -> str:
    body = uri.split("://", 1)[-1]
    return re.sub(r"[^a-zA-Z0-9_-]", "_", body)[:64]


def tools() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    used: set[str] = set()
    for route in fetch_routes():
        uri = str(route.get("uri") or "")
        name = tool_name(uri)
        while name in used:
            name = (name[:60] + "_x")[:64]
        used.add(name)
        out.append({
            "name": name,
            "description": route.get("title") or route.get("description") or uri,
            "inputSchema": route.get("inputSchema") or {"type": "object", "properties": {}},
            "_uri": uri,
        })
    return out


def tool_index() -> dict[str, str]:
    return {tool["name"]: tool["_uri"] for tool in tools()}


def run_uri(uri: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = {"uri": uri, "mode": "execute", "payload": payload or {}}
    resp = requests.post(runtime_url() + "/run", json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()


def respond(msg_id: Any, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> None:
    if msg_id is None:
        return
    body = {"jsonrpc": "2.0", "id": msg_id}
    body["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(body) + "\n")
    sys.stdout.flush()


def handle(req: dict[str, Any]) -> None:
    method = req.get("method")
    msg_id = req.get("id")
    if method == "initialize":
        respond(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": SERVER_INFO,
            "capabilities": {"tools": {}},
            "instructions": f"Runtime={runtime_url()} LLM_API_BASE={llm_api_base()}",
        })
        return
    if method == "tools/list":
        public = [{k: v for k, v in tool.items() if k != "_uri"} for tool in tools()]
        respond(msg_id, {"tools": public})
        return
    if method == "tools/call":
        params = req.get("params") or {}
        uri = tool_index().get(str(params.get("name") or ""))
        if not uri:
            respond(msg_id, error={"code": -32602, "message": "unknown tool"})
            return
        envelope = run_uri(uri, params.get("arguments") or {})
        respond(msg_id, {
            "content": [{"type": "text", "text": json.dumps(envelope, ensure_ascii=False)}],
            "isError": not bool(envelope.get("ok", True)),
        })
        return
    if method and method.startswith("notifications/"):
        return
    respond(msg_id, error={"code": -32601, "message": f"unknown method: {method}"})


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        handle(json.loads(line))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
