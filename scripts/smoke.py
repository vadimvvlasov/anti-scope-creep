"""Smoke test of a deployed backend: the full stub analysis flow through the public API.

Steps: wait for GET /health/ready, register a fresh user, paste a short English
contract, poll it every 2 s until `done`, check that it has findings and an email
draft, then delete the contract. Exits non-zero with a message on the first failure.

Usage:
    python3 scripts/smoke.py https://anti-scope-creep-dev.example.cs.amazonlightsail.com
    python3 scripts/smoke.py http://localhost:8000 --timeout 60
"""

import argparse
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

# English, so language detection accepts it; the stub analyzer finds several risks in it.
CONTRACT_TEXT = (
    "This Statement of Work is between Client and Freelancer. "
    "The Freelancer will design and build a marketing website. "
    "The Client may request additional revisions at any time at no extra cost. "
    "Payment is due within 90 days after final acceptance. "
    "The Freelancer assigns all intellectual property upon delivery. "
    "Either party may terminate this agreement with seven days written notice."
)


class SmokeError(Exception):
    pass


@dataclass
class Response:
    status: int
    body: dict | None


class Api:
    def __init__(self, base_url: str, request_timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.token: str | None = None

    def call(self, method: str, path: str, json_body: dict | None = None, form: dict | None = None) -> Response:
        headers = {"Accept": "application/json"}
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.request_timeout) as response:
                return Response(response.status, _json(response.read()))
        except urllib.error.HTTPError as error:
            return Response(error.code, _json(error.read()))


def _json(raw: bytes) -> dict | None:
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def _expect(response: Response, status: int, step: str) -> dict:
    if response.status != status:
        raise SmokeError(f"{step}: expected HTTP {status}, got {response.status}: {response.body}")
    return response.body or {}


def wait_until_ready(api: Api, deadline: float, interval: float) -> None:
    last = "no response"
    while time.monotonic() < deadline:
        try:
            response = api.call("GET", "/health/ready")
            if response.status == 200:
                return
            last = f"HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last = str(error)
        time.sleep(interval)
    raise SmokeError(f"health: /health/ready did not return 200 in time (last: {last})")


def wait_until_analyzed(api: Api, contract_id: str, deadline: float, interval: float) -> dict:
    while time.monotonic() < deadline:
        contract = _expect(api.call("GET", f"/contracts/{contract_id}"), 200, "poll")
        if contract.get("status") == "done":
            return contract
        if contract.get("status") == "failed":
            raise SmokeError(f"analysis: contract {contract_id} ended in status failed")
        time.sleep(interval)
    raise SmokeError(f"analysis: contract {contract_id} was not done in time")


def run(base_url: str, timeout: float = 120.0, interval: float = 2.0) -> None:
    api = Api(base_url)
    deadline = time.monotonic() + timeout
    wait_until_ready(api, deadline, interval)
    print("ok  health: ready")

    email = f"smoke-{int(time.time())}-{secrets.token_hex(3)}@example.com"
    auth = _expect(api.call("POST", "/auth/register", {"email": email, "password": secrets.token_urlsafe(16)}), 201, "register")
    api.token = auth["access_token"]
    print(f"ok  register: {email}")

    created = _expect(api.call("POST", "/contracts", form={"text": CONTRACT_TEXT, "title": "Smoke test"}), 202, "upload")
    contract = wait_until_analyzed(api, created["id"], deadline, interval)
    if not contract.get("findings") or not contract.get("email_draft"):
        raise SmokeError("analysis: done, but findings or the email draft are missing")
    print(f"ok  analysis: done, {len(contract['findings'])} findings and an email draft")

    _expect(api.call("DELETE", f"/contracts/{created['id']}"), 204, "delete")
    print("ok  cleanup: contract deleted")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_url", help="API base URL, e.g. https://<service>.<id>.<region>.cs.amazonlightsail.com")
    parser.add_argument("--timeout", type=float, default=120.0, help="seconds for the whole run (default 120)")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between polls (default 2)")
    args = parser.parse_args(argv)
    try:
        run(args.base_url, args.timeout, args.interval)
    except SmokeError as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    print("smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
