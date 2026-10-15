"""MCP server: a scoped, read-only view of Anti-Scope Creep for coding agents.

Three tools over the public API: service status, the account's contracts, and the findings
of one contract. Nothing writes, deletes or starts an analysis, and the full contract text
and the email draft are never returned.

Configuration (environment):
- ASC_API_URL: backend base URL, default http://localhost:8000. Only a local backend is
  allowed unless ASC_ALLOW_REMOTE=1, so an agent sees test data, not real users' contracts.
- ASC_EMAIL, ASC_PASSWORD: a test account on that backend. The token stays in memory.
"""

import os
from typing import Any
from urllib.parse import urlparse

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
SUMMARY_FIELDS = ("id", "title", "status", "overall_risk_level", "analyzed_at")
FINDING_FIELDS = ("category", "risk_level", "quoted_text", "explanation", "suggested_change")


class ApiClient:
    def __init__(self, base_url: str, email: str, password: str, transport: httpx.BaseTransport | None = None):
        self._http = httpx.Client(base_url=base_url, timeout=15, transport=transport)
        self._email, self._password = email, password
        self._token: str | None = None

    def get(self, path: str, *, auth: bool = True, **params: Any) -> Any:
        headers = {"Authorization": f"Bearer {self._login()}"} if auth else {}
        response = self._http.get(path, params=params, headers=headers)
        if response.status_code == 401 and auth:  # the 24-hour token expired
            self._token = None
            headers = {"Authorization": f"Bearer {self._login()}"}
            response = self._http.get(path, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    def _login(self) -> str:
        if self._token is None:
            if not (self._email and self._password):
                raise RuntimeError("Set ASC_EMAIL and ASC_PASSWORD for a test account")
            response = self._http.post("/auth/login", json={"email": self._email, "password": self._password})
            response.raise_for_status()
            self._token = response.json()["access_token"]
        return self._token


def check_base_url(url: str, allow_remote: bool) -> str:
    host = urlparse(url).hostname
    if host not in LOCAL_HOSTS and not allow_remote:
        raise ValueError(f"{url} is not a local backend; set ASC_ALLOW_REMOTE=1 to allow it")
    return url


def service_status(client: ApiClient) -> dict[str, Any]:
    return {
        "health": client.get("/health", auth=False),
        "ready": client.get("/health/ready", auth=False),
        "version": client.get("/version", auth=False),
    }


def list_contracts(client: ApiClient, page: int = 1) -> dict[str, Any]:
    data = client.get("/contracts", page=page, page_size=20)
    return {
        "page": data.get("page", page),
        "total_pages": data.get("total_pages"),
        "items": [{k: item.get(k) for k in SUMMARY_FIELDS} for item in data["items"]],
    }


def get_findings(client: ApiClient, contract_id: str) -> dict[str, Any]:
    data = client.get(f"/contracts/{contract_id}")
    return {
        **{k: data.get(k) for k in SUMMARY_FIELDS},
        "risk_summary": data.get("risk_summary"),
        "findings": [{k: f.get(k) for k in FINDING_FIELDS} for f in data.get("findings") or []],
    }


def build_server(client: ApiClient) -> MCPServer:
    server = MCPServer("anti-scope-creep")

    @server.tool(name="service_status", annotations=READ_ONLY)
    def _status() -> dict[str, Any]:
        """Health, database readiness and the deployed version of the configured backend."""
        return service_status(client)

    @server.tool(name="list_contracts", annotations=READ_ONLY)
    def _list(page: int = 1) -> dict[str, Any]:
        """The test account's contracts, newest first, 20 per page: id, title, status, overall risk."""
        return list_contracts(client, page)

    @server.tool(name="get_findings", annotations=READ_ONLY)
    def _findings(contract_id: str) -> dict[str, Any]:
        """Findings of one contract from its last successful analysis: category, risk level,
        quoted clause, explanation and suggested change. The full text is not returned."""
        return get_findings(client, contract_id)

    return server


def main() -> None:
    url = check_base_url(os.environ.get("ASC_API_URL", "http://localhost:8000"), os.environ.get("ASC_ALLOW_REMOTE") == "1")
    client = ApiClient(url, os.environ.get("ASC_EMAIL", ""), os.environ.get("ASC_PASSWORD", ""))
    build_server(client).run()


if __name__ == "__main__":
    main()
