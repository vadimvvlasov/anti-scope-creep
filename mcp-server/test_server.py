"""Tests for the MCP server with a fake backend: uv run python -m unittest (from mcp-server/)"""

import asyncio
import json
import unittest

import httpx

import server

CONTRACT = {
    "id": "c1", "title": "Acme MSA", "status": "analyzed", "overall_risk_level": "high",
    "analyzed_at": "2026-10-15T10:00:00Z", "filename": "acme.pdf", "source_text": "FULL CONTRACT TEXT",
    "risk_summary": {"high": 1, "medium": 0, "low": 0},
    "findings": [{
        "id": "f1", "category": "ip_transfer_before_payment", "risk_level": "high",
        "quoted_text": "All rights vest in Client.", "explanation": "e", "suggested_change": "s",
        "start_char": 0, "end_char": 26,
    }],
    "email_draft": {"subject": "x", "body": "EMAIL BODY"},
}


class FakeBackend:
    def __init__(self):
        self.logins = 0
        self.expire_next = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/auth/login":
            self.logins += 1
            return httpx.Response(200, json={"access_token": f"t{self.logins}", "token_type": "bearer"})
        if path.startswith("/health") or path == "/version":
            return httpx.Response(200, json={"status": "ok"} if path != "/version" else {"version": "sha-1234567"})
        if request.headers.get("Authorization") != f"Bearer t{self.logins}" or self.expire_next:
            self.expire_next = False
            return httpx.Response(401, json={"error": {"code": "unauthorized"}})
        if path == "/contracts":
            return httpx.Response(200, json={"items": [CONTRACT], "page": 1, "total_pages": 1})
        if path == "/contracts/c1":
            return httpx.Response(200, json=CONTRACT)
        return httpx.Response(404, json={"error": {"code": "contract_not_found"}})


def client(backend: FakeBackend) -> server.ApiClient:
    return server.ApiClient("http://localhost:8000", "test@example.com", "pw", transport=httpx.MockTransport(backend))


class ToolsTest(unittest.TestCase):
    def test_findings_leave_out_the_contract_text_and_the_email(self):
        result = server.get_findings(client(FakeBackend()), "c1")
        self.assertEqual(result["findings"][0]["quoted_text"], "All rights vest in Client.")
        dumped = json.dumps(result)
        self.assertNotIn("FULL CONTRACT TEXT", dumped)
        self.assertNotIn("EMAIL BODY", dumped)
        self.assertNotIn("acme.pdf", dumped)

    def test_list_returns_summaries_only(self):
        result = server.list_contracts(client(FakeBackend()))
        self.assertEqual(result["items"], [{k: CONTRACT[k] for k in server.SUMMARY_FIELDS}])

    def test_status_needs_no_login(self):
        backend = FakeBackend()
        self.assertEqual(server.service_status(client(backend))["version"], {"version": "sha-1234567"})
        self.assertEqual(backend.logins, 0)

    def test_an_expired_token_is_renewed_once(self):
        backend = FakeBackend()
        api = client(backend)
        server.list_contracts(api)
        backend.expire_next = True
        server.list_contracts(api)
        self.assertEqual(backend.logins, 2)

    def test_unknown_contract_raises(self):
        with self.assertRaises(httpx.HTTPStatusError):
            server.get_findings(client(FakeBackend()), "nope")

    def test_missing_credentials_are_reported(self):
        api = server.ApiClient("http://localhost:8000", "", "", transport=httpx.MockTransport(FakeBackend()))
        with self.assertRaisesRegex(RuntimeError, "ASC_EMAIL"):
            server.list_contracts(api)


class ScopeTest(unittest.TestCase):
    def test_only_a_local_backend_unless_allowed(self):
        self.assertEqual(server.check_base_url("http://127.0.0.1:8000", False), "http://127.0.0.1:8000")
        with self.assertRaises(ValueError):
            server.check_base_url("https://api.example.com", False)
        self.assertEqual(server.check_base_url("https://api.example.com", True), "https://api.example.com")

    def test_the_server_exposes_three_read_only_tools(self):
        tools = asyncio.run(server.build_server(client(FakeBackend())).list_tools())
        self.assertEqual(sorted(t.name for t in tools), ["get_findings", "list_contracts", "service_status"])


if __name__ == "__main__":
    unittest.main()
