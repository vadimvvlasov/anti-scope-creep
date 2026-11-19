"""Measure analysis times of a deployed backend through its public API (issue #121).

Two phases, each with fresh users (registration allows 5 per IP per hour, so 1 + N must stay <= 5):

1. cold: one analysis, started when the local model is asleep (no request for 6+ minutes), so it
   includes loading the model; skip it with --skip-cold;
2. concurrent: N users upload the same contract at the same moment; with one llama-server slot the
   last one waits for the others. Starts right after phase 1, so the model is warm.

Prints a Markdown table (seconds from upload to `done` or `failed`) for docs/self-host.md and
deletes the contracts. The contract text comes from a file, e.g. a synthetic one from data/.

Usage:
    python3 scripts/measure_analysis.py https://asc-dev.example.ts.net --contract data/4.txt
    python3 scripts/measure_analysis.py http://localhost:8000 --contract data/4.txt --skip-cold -n 2
"""

import argparse
import secrets
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from smoke import Api, SmokeError, _expect, wait_until_ready


@dataclass
class Result:
    phase: str
    label: str
    status: str
    seconds: float
    findings: int


# The backend can be slow to answer an upload while the local model is busy; 15 s (the smoke default) is too short.
REQUEST_TIMEOUT = 60.0


def register(base_url: str) -> Api:
    api = Api(base_url, REQUEST_TIMEOUT)
    email = f"measure-{int(time.time())}-{secrets.token_hex(3)}@example.com"
    body = {"email": email, "password": secrets.token_urlsafe(16)}
    api.token = _expect(api.call("POST", "/auth/register", body), 201, "register")["access_token"]
    return api


def analyze(api: Api, text: str, title: str, deadline: float, interval: float) -> tuple[str, int, str]:
    """Upload and poll until the analysis ends; returns (status, findings, contract id)."""
    created = _expect(api.call("POST", "/contracts", form={"text": text, "title": title}), 202, "upload")
    while time.monotonic() < deadline:
        try:
            contract = _expect(api.call("GET", f"/contracts/{created['id']}"), 200, "poll")
        except OSError:  # a timeout or dropped connection on one poll must not end a minutes-long measurement
            time.sleep(interval)
            continue
        if contract.get("status") in ("done", "failed"):
            return contract["status"], len(contract.get("findings") or []), created["id"]
        time.sleep(interval)
    return "timeout", 0, created["id"]


def timed(phase: str, label: str, api: Api, text: str, deadline: float, interval: float) -> Result:
    start = time.monotonic()
    try:
        status, findings, contract_id = analyze(api, text, f"Measure {label}", deadline, interval)
    except OSError as error:  # name the analysis: "read operation timed out" alone says nothing
        raise SmokeError(f"{phase} {label}: upload failed after {time.monotonic() - start:.0f} s: {error}") from error
    seconds = time.monotonic() - start
    print(f"{phase} {label}: {status} in {seconds:.0f} s", file=sys.stderr)
    if status != "timeout":
        try:
            _expect(api.call("DELETE", f"/contracts/{contract_id}"), 204, "delete")
        except (OSError, SmokeError) as error:  # the measurement is done; a leftover test contract is harmless
            print(f"warning: contract {contract_id} not deleted: {error}", file=sys.stderr)
    return Result(phase, label, status, seconds, findings)


def run_concurrent(apis: list[Api], text: str, deadline: float, interval: float) -> list[Result]:
    results: list[Result | None] = [None] * len(apis)
    errors: list[Exception] = []
    barrier = threading.Barrier(len(apis))

    def worker(i: int) -> None:
        try:
            barrier.wait()
            results[i] = timed("concurrent", f"{i + 1} of {len(apis)}", apis[i], text, deadline, interval)
        except Exception as error:  # reported after all threads end
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(apis))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if errors:
        raise SmokeError(f"concurrent: {errors[0]}")
    return sorted((r for r in results if r), key=lambda r: r.seconds)


def table(results: list[Result], chars: int) -> str:
    rows = ["| Phase | Analysis | Status | Seconds | Findings |", "|---|---|---|---|---|"]
    for r in results:
        rows.append(f"| {r.phase} | {r.label} | {r.status} | {r.seconds:.0f} | {r.findings} |")
    return f"Contract: {chars:,} characters.\n\n" + "\n".join(rows)


def run(base_url: str, text: str, concurrent: int, skip_cold: bool, timeout: float, interval: float) -> list[Result]:
    deadline = time.monotonic() + timeout
    wait_until_ready(Api(base_url), deadline, interval)
    apis = [register(base_url) for _ in range(concurrent + (0 if skip_cold else 1))]
    results: list[Result] = []
    if not skip_cold:
        results.append(timed("cold", "1 of 1", apis.pop(0), text, deadline, interval))
        print(f"cold: {results[-1].status} in {results[-1].seconds:.0f} s", file=sys.stderr)
    results += run_concurrent(apis, text, deadline, interval)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_url", help="API base URL, e.g. https://asc-dev.<tailnet>.ts.net")
    parser.add_argument("--contract", required=True, type=Path, help="text file with an English contract")
    parser.add_argument("-n", "--concurrent", type=int, default=3, help="simultaneous analyses (default 3)")
    parser.add_argument("--skip-cold", action="store_true", help="skip the single cold-start analysis")
    parser.add_argument("--timeout", type=float, default=2400.0, help="seconds for the whole run (default 2400)")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between polls (default 5)")
    args = parser.parse_args(argv)
    if args.concurrent + (0 if args.skip_cold else 1) > 5:
        parser.error("registration allows 5 users per IP per hour: lower -n or add --skip-cold")
    text = args.contract.read_text(encoding="utf-8")
    try:
        results = run(args.base_url, text, args.concurrent, args.skip_cold, args.timeout, args.interval)
    except SmokeError as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    print(table(results, len(text)))
    return 0 if all(r.status == "done" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
