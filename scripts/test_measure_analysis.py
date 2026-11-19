"""Tests for measure_analysis.py against a fake API. Run: python3 -m unittest discover scripts"""

import io
import json
import threading
import unittest
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from measure_analysis import main


class FakeApi:
    """Every user gets a token; each contract is `done` (or `failed`) on its second poll."""

    def __init__(self, final: str = "done", drop_first_poll: bool = False):
        self.final = final
        self.drop_next_poll = drop_first_poll
        self.lock = threading.Lock()
        self.users = 0
        self.polls: dict[str, int] = {}
        self.deleted: list[str] = []

    def handle(self, method: str, path: str, headers: dict, body: bytes) -> tuple[int, dict | None]:
        with self.lock:
            if path == "/health/ready":
                return 200, {"status": "ok"}
            if (method, path) == ("POST", "/auth/register"):
                self.users += 1
                return 201, {"access_token": f"t{self.users}"}
            if not headers.get("Authorization", "").startswith("Bearer t"):
                return 401, None
            if (method, path) == ("POST", "/contracts"):
                contract_id = f"c{len(self.polls) + 1}"
                self.polls[contract_id] = 0
                return 202, {"id": contract_id, "status": "analyzing"}
            contract_id = path.rsplit("/", 1)[-1]
            if method == "DELETE":
                self.deleted.append(contract_id)
                return 204, None
            if self.drop_next_poll:
                self.drop_next_poll = False
                return 0, None  # the handler closes the connection without a reply
            self.polls[contract_id] += 1
            done = self.polls[contract_id] >= 2
            status = self.final if done else "analyzing"
            return 200, {"id": contract_id, "status": status, "findings": [{}, {}] if status == "done" else []}


def serve(api: FakeApi) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _reply(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            status, payload = api.handle(self.command, self.path, dict(self.headers), body)
            if status == 0:
                self.close_connection = True
                return
            data = json.dumps(payload).encode() if payload is not None else b""
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_DELETE = _reply

        def log_message(self, *args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class MeasureTest(unittest.TestCase):
    def run_main(self, api: FakeApi, *extra: str) -> tuple[int, str]:
        server = serve(api)
        self.addCleanup(server.shutdown)
        with TemporaryDirectory() as tmp:
            contract = Path(tmp) / "c.txt"
            contract.write_text("An English contract.", encoding="utf-8")
            url = f"http://127.0.0.1:{server.server_port}"
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main([url, "--contract", str(contract), "--interval", "0.01", *extra])
        return code, out.getvalue()

    def test_cold_then_three_concurrent(self) -> None:
        api = FakeApi()
        code, out = self.run_main(api)
        self.assertEqual(code, 0)
        self.assertEqual(api.users, 4)
        self.assertEqual(sorted(api.deleted), ["c1", "c2", "c3", "c4"])
        self.assertIn("| cold | 1 of 1 | done |", out)
        self.assertEqual(out.count("| concurrent |"), 3)
        self.assertIn("Contract: 20 characters.", out)

    def test_a_dropped_poll_is_retried(self) -> None:
        code, out = self.run_main(FakeApi(drop_first_poll=True), "--skip-cold", "-n", "1")
        self.assertEqual(code, 0)
        self.assertIn("| concurrent | 1 of 1 | done |", out)

    def test_failed_analysis_is_reported_and_exits_non_zero(self) -> None:
        code, out = self.run_main(FakeApi(final="failed"), "--skip-cold", "-n", "2")
        self.assertEqual(code, 1)
        self.assertEqual(out.count("| failed |"), 2)

    def test_an_upload_that_fails_names_the_analysis(self) -> None:
        with mock.patch("measure_analysis.analyze", side_effect=TimeoutError("The read operation timed out")):
            code, out = self.run_main(FakeApi(), "--skip-cold", "-n", "1")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")

    def test_refuses_more_users_than_registration_allows(self) -> None:
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            main(["http://127.0.0.1:1", "--contract", "x", "-n", "5"])


if __name__ == "__main__":
    unittest.main()
