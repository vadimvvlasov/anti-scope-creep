"""Tests for wait_version.py against a fake backend. Run: python3 -m unittest discover scripts"""

import io
import json
import socket
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wait_version import main


class FakeBackend:
    """Answers GET /version from a script of (status, version) pairs; the last one repeats."""

    def __init__(self, *answers: tuple[int, str]):
        self.answers = list(answers)
        self.calls = 0

    def next(self) -> tuple[int, str]:
        self.calls += 1
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def serve(backend: FakeBackend) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            status, version = backend.next() if self.path == "/version" else (404, "")
            data = json.dumps({"version": version}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class WaitVersionTest(unittest.TestCase):
    def run_wait(self, url: str, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([url, "sha-new0001", "--interval", "0.01", *args])
        return code, out.getvalue(), err.getvalue()

    def start(self, *answers: tuple[int, str]) -> tuple[FakeBackend, str]:
        backend = FakeBackend(*answers)
        server = serve(backend)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return backend, f"http://127.0.0.1:{server.server_port}"

    def test_returns_at_once_when_the_version_is_already_there(self):
        backend, url = self.start((200, "sha-new0001"))
        code, out, _ = self.run_wait(url)
        self.assertEqual(code, 0)
        self.assertIn("ok  version: sha-new0001", out)
        self.assertEqual(backend.calls, 1)

    def test_waits_through_the_old_version_and_a_restart(self):
        backend, url = self.start((200, "sha-old0001"), (200, "sha-old0001"), (503, ""), (200, "sha-new0001"))
        code, out, _ = self.run_wait(url, "--timeout", "5")
        self.assertEqual(code, 0)
        self.assertEqual(backend.calls, 4)
        # One line per change of what the server reports, not per poll.
        self.assertEqual(out.count("the server reports: sha-old0001"), 1)
        self.assertIn("the server reports: HTTP 503", out)

    def test_times_out_with_a_hint_about_the_server_timer(self):
        _, url = self.start((200, "sha-old0001"))
        code, _, err = self.run_wait(url, "--timeout", "0.2")
        self.assertEqual(code, 1)
        self.assertIn("did not report sha-new0001", err)
        self.assertIn("(last: sha-old0001)", err)
        self.assertIn("asc-pull.timer", err)

    def test_unreachable_server_counts_as_not_yet(self):
        code, out, err = self.run_wait(f"http://127.0.0.1:{free_port()}", "--timeout", "0.2")
        self.assertEqual(code, 1)
        self.assertIn("no answer", out)
        self.assertIn("last: no answer", err)


if __name__ == "__main__":
    unittest.main()
