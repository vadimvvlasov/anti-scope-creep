# MCP server

A read-only view of Anti-Scope Creep for coding agents, over the public API
(stdio transport, [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) 2.x).

| Tool | Returns |
|---|---|
| `service_status` | `/health`, `/health/ready` and `/version` of the backend (no login) |
| `list_contracts(page)` | the test account's contracts, 20 per page: id, title, status, overall risk, analyzed at |
| `get_findings(contract_id)` | risk summary and findings: category, risk level, quoted clause, explanation, suggested change |

Never returned: the full contract text, the email draft, the file name. Nothing writes.

## Run

```bash
make up                                  # local stack on http://localhost:8000
# register a test account in the app (http://localhost:3000), then:
export ASC_EMAIL=you@example.com ASC_PASSWORD=...
```

Claude Code starts the server from the repository's `.mcp.json`
(`uv run --directory mcp-server python server.py`); approve it once in `/mcp`. Any other
MCP client can run the same command.

| Variable | Default | Meaning |
|---|---|---|
| `ASC_API_URL` | `http://localhost:8000` | backend base URL |
| `ASC_ALLOW_REMOTE` | unset | `1` allows a non-local backend (dev or prod); off by default so the agent sees test data |
| `ASC_EMAIL`, `ASC_PASSWORD` | none | a test account; the token stays in memory |

## Test

```bash
uv run python -m unittest
```

The tests use a fake backend (`httpx.MockTransport`), no network.
