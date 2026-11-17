"""Tests for server-pull.sh with a fake docker on PATH. Run: python3 -m unittest discover scripts"""

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("server-pull.sh")

# The fake docker keeps one file per environment in FAKE_STATE: <env>.cid is the running backend container,
# <env>.new the container that `up` starts next (a new image was pulled). FAKE_FAIL lists "<command>:<env>"
# pairs that must fail, FAKE_PRUNE what `image prune` prints. Every call is appended to FAKE_STATE/calls.
FAKE_DOCKER = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import os, sys
    from pathlib import Path

    state = Path(os.environ["FAKE_STATE"])
    args = sys.argv[1:]
    with open(state / "calls", "a") as calls:
        calls.write(" ".join(args) + "\\n")

    if args[0] == "compose":
        env = Path(args[args.index("--env-file") + 1]).stem
        command = args[args.index("--env-file") + 2]
        if f"{command}:{env}" in os.environ.get("FAKE_FAIL", "").split():
            sys.exit(1)
        cid, new = state / f"{env}.cid", state / f"{env}.new"
        if command == "ps" and cid.exists():
            print(cid.read_text())
        if command == "up" and new.exists():
            new.rename(cid)
    elif args[0] == "network":
        fail = os.environ.get("FAKE_FAIL", "").split()
        if args[1] == "inspect" and os.environ.get("FAKE_NETWORK") == "missing":
            sys.exit(1)
        if args[1] == "create" and "network-create" in fail:
            sys.exit(1)
    elif args[0] == "inspect":
        print("sha256:image-" + args[-1])
    elif args[:2] == ["image", "inspect"]:
        version = "" if "c-local" in args[-1] else "\\nAPP_VERSION=sha-abc1234"
        print("PATH=/app/.venv/bin" + version + "\\nLANG=C.UTF-8")
    elif args[:2] == ["image", "prune"]:
        print(os.environ.get("FAKE_PRUNE", "Total reclaimed space: 0B"))
    """
)


class ServerPullTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        docker = self.bin / "docker"
        docker.write_text(FAKE_DOCKER)
        docker.chmod(0o755)
        self.compose_file = self.dir / "compose.server.yaml"
        self.compose_file.write_text("name: test\n")
        self.prod = self.env_file("prod")
        self.dev = self.env_file("dev")

    def env_file(self, name: str) -> Path:
        path = self.dir / f"{name}.env"
        path.write_text(f"COMPOSE_PROJECT_NAME=asc-{name}\n")
        return path

    def container(self, env: str, running: str | None = None, next_one: str | None = None) -> None:
        if running:
            (self.dir / f"{env}.cid").write_text(running)
        if next_one:
            (self.dir / f"{env}.new").write_text(next_one)

    def run_script(self, *args: Path | str, **fake: str) -> tuple[int, str]:
        env = {
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "HOME": str(self.dir),
            "FAKE_STATE": str(self.dir),
            "ASC_COMPOSE_FILE": str(self.compose_file),
            **fake,
        }
        result = subprocess.run(
            ["bash", str(SCRIPT), *map(str, args)], env=env, capture_output=True, text=True, timeout=30
        )
        return result.returncode, result.stdout + result.stderr

    def calls(self) -> list[str]:
        path = self.dir / "calls"
        return path.read_text().splitlines() if path.exists() else []

    def test_unchanged_environments_are_up_to_date(self):
        self.container("prod", running="c-prod")
        self.container("dev", running="c-dev")
        code, out = self.run_script(self.prod, self.dev)
        self.assertEqual(code, 0, out)
        self.assertIn("prod: up to date", out)
        self.assertIn("dev: up to date", out)
        self.assertNotIn("Total reclaimed", out)

    def test_pulls_and_waits_for_health_in_each_environment(self):
        self.run_script(self.prod, self.dev)
        prefix = f"compose --progress quiet -f {self.compose_file} --env-file"
        for env_file in (self.prod, self.dev):
            self.assertIn(f"{prefix} {env_file} pull --quiet", self.calls())
            self.assertIn(f"{prefix} {env_file} up -d --wait --wait-timeout 180", self.calls())
        self.assertEqual(self.calls()[-1], "image prune -f")

    def test_new_image_logs_its_version(self):
        self.container("prod", running="c-old", next_one="c-new")
        code, out = self.run_script(self.prod)
        self.assertEqual(code, 0, out)
        self.assertIn("prod: started sha-abc1234", out)
        self.assertNotIn("LANG=", out)

    def test_image_without_version_logs_its_id(self):
        self.container("prod", running="c-old", next_one="c-local-0123456789abcdef")
        code, out = self.run_script(self.prod)
        self.assertEqual(code, 0, out)
        self.assertIn("prod: started image image-c-loca\n", out)

    def test_first_start_counts_as_new(self):
        self.container("dev", next_one="c-dev")
        code, out = self.run_script(self.dev)
        self.assertEqual(code, 0, out)
        self.assertIn("dev: started sha-abc1234", out)

    def test_failed_environment_does_not_stop_the_others(self):
        code, out = self.run_script(self.prod, self.dev, FAKE_FAIL="up:prod")
        self.assertEqual(code, 1)
        self.assertIn("prod: not healthy after 180s", out)
        self.assertIn("dev: up to date", out)
        self.assertEqual(self.calls()[-1], "image prune -f")

    def test_failed_pull_skips_up(self):
        code, out = self.run_script(self.prod, FAKE_FAIL="pull:prod")
        self.assertEqual(code, 1)
        self.assertIn("prod: pull failed", out)
        self.assertFalse(any(" up " in call for call in self.calls()))

    def test_missing_env_file_fails(self):
        code, out = self.run_script(self.dir / "staging.env", self.dev)
        self.assertEqual(code, 1)
        self.assertIn("staging: cannot read", out)
        self.assertIn("dev: up to date", out)

    def test_wait_timeout_is_configurable(self):
        self.run_script(self.prod, ASC_WAIT_TIMEOUT="30")
        self.assertTrue(any(call.endswith("up -d --wait --wait-timeout 30") for call in self.calls()))

    def test_prune_output_is_logged_only_when_something_was_deleted(self):
        code, out = self.run_script(self.prod, FAKE_PRUNE="Deleted Images:\ndeleted: sha256:old\n\nTotal reclaimed space: 90MB")
        self.assertEqual(code, 0, out)
        self.assertIn("Total reclaimed space: 90MB", out)

    def test_existing_llm_network_is_left_alone(self):
        code, out = self.run_script(self.prod)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.calls()[0], "network inspect llm-api")
        self.assertNotIn("network create --internal llm-api", self.calls())

    def test_missing_llm_network_is_created_internal_before_any_environment(self):
        code, out = self.run_script(self.prod, FAKE_NETWORK="missing")
        self.assertEqual(code, 0, out)
        self.assertIn("created network llm-api", out)
        self.assertEqual(self.calls()[:2], ["network inspect llm-api", "network create --internal llm-api"])

    def test_llm_network_that_cannot_be_created_stops_the_run(self):
        code, out = self.run_script(self.prod, FAKE_NETWORK="missing", FAKE_FAIL="network-create")
        self.assertEqual(code, 1)
        self.assertIn("cannot create network llm-api", out)
        self.assertFalse(any(call.startswith("compose") for call in self.calls()))

    def test_no_arguments_prints_usage(self):
        code, out = self.run_script()
        self.assertEqual(code, 2)
        self.assertIn("usage:", out)
        self.assertEqual(self.calls(), [])

    def test_missing_compose_file_fails_before_docker(self):
        self.compose_file.unlink()
        code, out = self.run_script(self.prod)
        self.assertEqual(code, 1)
        self.assertIn("cannot read", out)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
