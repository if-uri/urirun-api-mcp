from __future__ import annotations

import json

from urirun_api_mcp import server


class Response:
    def __init__(self, data, error=False):
        self.data = data
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise RuntimeError("request failed")

    def json(self):
        return self.data


def test_tool_name_is_protocol_safe_and_bounded():
    name = server.tool_name("screen://host/path with spaces/" + "x" * 100)

    assert len(name) == 64
    assert " " not in name
    assert "/" not in name


def test_fetch_routes_falls_back_and_normalizes_registry(monkeypatch):
    calls = []

    def get(url, timeout):
        calls.append((url, timeout))
        if url == "http://127.0.0.1:8765/routes":
            return Response({}, error=True)
        return Response({"routes": {"one": {"uri": "test://one"}, "invalid": {"title": "ignored"}}})

    monkeypatch.setattr(server.requests, "get", get)

    assert server.fetch_routes() == [{"uri": "test://one"}]
    assert [url for url, _ in calls] == [
        "http://127.0.0.1:8765/routes",
        "http://127.0.0.1:8765/api/routes",
    ]


def test_tools_have_unique_names(monkeypatch):
    monkeypatch.setattr(
        server,
        "fetch_routes",
        lambda: [
            {"uri": "test://same", "title": "First"},
            {"uri": "other://same", "title": "Second"},
        ],
    )

    tools = server.tools()

    assert len({tool["name"] for tool in tools}) == 2
    assert all(tool["inputSchema"]["type"] == "object" for tool in tools)


def test_initialize_returns_connector_identity(capsys):
    server.handle({"jsonrpc": "2.0", "id": 7, "method": "initialize"})

    response = json.loads(capsys.readouterr().out)
    assert response["id"] == 7
    assert response["result"]["serverInfo"]["name"] == "urirun-connector-mcp"


def test_tool_call_forwards_arguments(monkeypatch, capsys):
    monkeypatch.setattr(server, "tool_index", lambda: {"demo": "test://demo"})
    monkeypatch.setattr(
        server,
        "run_uri",
        lambda uri, payload: {"ok": True, "uri": uri, "payload": payload},
    )

    server.handle(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "demo", "arguments": {"value": 3}},
        }
    )

    response = json.loads(capsys.readouterr().out)
    envelope = json.loads(response["result"]["content"][0]["text"])
    assert envelope == {"ok": True, "uri": "test://demo", "payload": {"value": 3}}
