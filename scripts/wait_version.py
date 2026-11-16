"""Wait until a deployed backend reports the expected version on GET /version.

The home server pulls new images itself, on a timer (asc-pull.timer, every 5 minutes; docs/self-host.md).
A deploy workflow moves the environment tag in ghcr and then waits here until the server runs the new image.
Network and TLS errors count as "not yet": the backend restarts during the switch, and a Funnel node that has
just appeared drops some TLS handshakes for a few minutes.

Usage:
    python3 scripts/wait_version.py <BACKEND-URL> sha-1a2b3c4
    python3 scripts/wait_version.py <BACKEND-URL> sha-1a2b3c4 --timeout 600 --interval 15
"""

import argparse
import sys
import time

from smoke import Api

HINT = (
    "The server pulls new images every 5 minutes (asc-pull.timer). On the server, check "
    "`systemctl status asc-pull.timer asc-pull.service` and `journalctl -u asc-pull.service -n 50` "
    "(docs/self-host.md, section 5)."
)


def current_version(api: Api) -> str:
    """What GET /version reports now, or why it could not be read."""
    try:
        response = api.call("GET", "/version")
    except OSError as error:  # URLError, TLS and connection errors, timeouts
        return f"no answer ({error})"
    if response.status != 200:
        return f"HTTP {response.status}"
    return str((response.body or {}).get("version"))


def wait_for_version(api: Api, expected: str, timeout: float, interval: float) -> bool:
    """Poll until GET /version returns `expected`; print each change of what the server reports."""
    deadline = time.monotonic() + timeout
    last = None
    while True:
        seen = current_version(api)
        if seen == expected:
            print(f"ok  version: {expected}")
            return True
        if seen != last:
            print(f"..  waiting for {expected}, the server reports: {seen}", flush=True)
            last = seen
        if time.monotonic() + interval > deadline:
            print(f"FAIL GET /version did not report {expected} in {timeout:.0f} s (last: {seen}). {HINT}", file=sys.stderr)
            return False
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_url", help="API base URL, e.g. https://asc-dev.<tailnet>.ts.net")
    parser.add_argument("version", help="the version to wait for, e.g. sha-1a2b3c4")
    parser.add_argument("--timeout", type=float, default=600.0, help="seconds to wait in total (default 600)")
    parser.add_argument("--interval", type=float, default=15.0, help="seconds between polls (default 15)")
    args = parser.parse_args(argv)
    api = Api(args.base_url, request_timeout=10.0)
    return 0 if wait_for_version(api, args.version, args.timeout, args.interval) else 1


if __name__ == "__main__":
    sys.exit(main())
