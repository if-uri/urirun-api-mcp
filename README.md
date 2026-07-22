# urirun-connector-mcp

Thin MCP connector for `urirun` based on the live runtime registry exposed by `urirun` and the LLM-facing conventions from `urirun-llm-runtime`.

The import path `urirun_api_mcp` and command `urirun-api-mcp` remain available for backward compatibility. New integrations should use `urirun-connector-mcp`.

## Purpose

- fetch full runtime registry from `GET /routes`
- project every URI route into an MCP tool with `inputSchema`
- forward `tools/call` to `POST /run`
- let operators switch LLM transport between:
  - `https://llm.urirun.com/api/v1`
  - direct OpenRouter

## Environment

See `.env.example`.

Key variables:

- `URIRUN_RUNTIME_URL` — `urirun` node base URL
- `URIRUN_LLM_API_BASE` — OpenAI-compatible proxy base, e.g. `https://llm.urirun.com/api/v1`
- `OPENROUTER_BASE_URL` — direct OpenRouter fallback

## Run

```bash
cp .env.example .env
pip install -e .
urirun-connector-mcp
```

The process speaks line-delimited JSON-RPC 2.0 over stdio and implements:

- `initialize`
- `tools/list`
- `tools/call`
