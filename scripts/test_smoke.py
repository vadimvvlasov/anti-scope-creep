"""Tests for smoke.py against a fake API server. Run: python3 -m unittest discover scripts"""

import io
import json
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from smoke import main

CONTRACT_ID = "3f2b9c1e-0000-4000-8000-000000000000"


class FakeApi:
    """Scripted backend: readiness and the contract status sequence are configurable."""

    def __init__(self, ready_after: int = 0, statuses: tuple[str, ...] = ("analyzing", "done"), findings: int = 3):
        self.ready_after = ready_after
        self.statuses = list(statuses)
        self.findings = findings
        self.requests: list[tuple[str, str, dict]] = []

    def handle(self, method: str, path: str, headers: dict, body: bytes) -> tuple[int, dict | None]:
        self.requests.append((method, path, headers))
        if path == "/health/ready":
            if self.ready_after > 0:
                self.ready_after -= 1
                return 503, {"status": "unavailable"}
            return 200, {"status": "ok"}
        if (method, path) == ("POST", "/auth/register"):
            return 201, {"access_token": "token", "user": {"email": json.loads(body)["email"]}}
        if headers.get("Authorization") != "Bearer token":
            return 401, {"error": {"code": "UNAUTHORIZED"}}
        if (method, path) == ("POST", "/contracts"):
            form = parse_qs(body.decode())
            assert form["title"] == ["Smoke test"] and form["text"][0].startswith("This Statement")
            return 202, {"id": CONTRACT_ID, "status": "analyzing"}
        if (method, path) == ("GET", f"/contracts/{CONTRACT_ID}"):
            status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            done = status == "done"
            return 200, {
                "id": CONTRACT_ID,
                "status": status,
                "findings": [{"category": "x"}] * self.findings if done else [],
                "email_draft": {"subject": "s", "body": "b"} if done else None,
            }
        if (method, path) == ("DELETE", f"/contracts/{CONTRACT_ID}"):
            return 204, None
        return 404, {"error": {"code": "NOT_FOUND"}}


def serve(api: FakeApi) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _respond(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            status, payload = api.handle(self.command, self.path, dict(self.headers), body)
            data = json.dumps(payload).encode() if payload is not None else b""
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_DELETE = _respond

        def log_message(self, *args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class SmokeTest(unittest.TestCase):
    def run_smoke(self, api: FakeApi, timeout: str = "5") -> tuple[int, str, str]:
        server = serve(api)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([url, "--timeout", timeout, "--interval", "0.01"])
        return code, out.getvalue(), err.getvalue()

    def test_full_flow_passes_and_deletes_the_contract(self):
        api = FakeApi(ready_after=2)
        code, out, err = self.run_smoke(api)
        self.assertEqual(code, 0, err)
        self.assertIn("smoke test passed", out)
        self.assertIn(("DELETE", f"/contracts/{CONTRACT_ID}"), [(m, p) for m, p, _ in api.requests])

    def test_failed_analysis_exits_non_zero(self):
        code, _, err = self.run_smoke(FakeApi(statuses=("analyzing", "failed")))
        self.assertEqual(code, 1)
        self.assertIn("ended in status failed", err)

    def test_done_without_findings_exits_non_zero(self):
        code, _, err = self.run_smoke(FakeApi(findings=0))
        self.assertEqual(code, 1)
        self.assertIn("findings or the email draft are missing", err)

    def test_backend_that_never_gets_ready_times_out(self):
        code, _, err = self.run_smoke(FakeApi(ready_after=10_000), timeout="0.3")
        self.assertEqual(code, 1)
        self.assertIn("/health/ready did not return 200", err)


if __name__ == "__main__":
    unittest.main()
