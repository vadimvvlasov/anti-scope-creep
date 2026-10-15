"""Tests for the PreToolUse guard: python3 -m unittest discover -s agent-hooks"""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import guard

GUARD = Path(__file__).with_name("guard.py")


def bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


class FileToolTest(unittest.TestCase):
    def test_secret_files_are_blocked(self):
        for path in (".env", "backend/.env", "/home/u/.config/gemini.env", ".env.local", "deploy/key.pem", "~/.ssh/id_rsa"):
            with self.subTest(path=path):
                self.assertIsNotNone(guard.check({"tool_name": "Read", "tool_input": {"file_path": path}}))

    def test_ordinary_files_and_the_example_are_allowed(self):
        for path in ("backend/.env.example", "docs/spec.md", "backend/app/config.py", "frontend/src/env.ts"):
            with self.subTest(path=path):
                self.assertIsNone(guard.check({"tool_name": "Edit", "tool_input": {"file_path": path}}))

    def test_grep_over_a_secret_file_is_blocked(self):
        self.assertIsNotNone(guard.check({"tool_name": "Grep", "tool_input": {"pattern": "KEY", "path": "backend/.env"}}))


class CommandTest(unittest.TestCase):
    def test_reading_or_printing_secrets_is_blocked(self):
        for command in ("cat backend/.env", "grep KEY ~/.config/groq.env", "printenv", "env | sort",
                        "echo $GROQ_API_KEY", "head -3 .env && ls"):
            with self.subTest(command=command):
                self.assertIsNotNone(guard.check(bash(command)))

    def test_loading_a_key_without_printing_it_is_allowed(self):
        for command in ("set -a; source ~/.config/gemini.env; set +a", "source .env && uv run pytest",
                        "cat backend/.env.example", "uv run pytest", "env_file=x; ls"):
            with self.subTest(command=command):
                self.assertIsNone(guard.check(bash(command)))

    def test_credentials_reserved_for_the_developer_are_blocked(self):
        for command in ("aws lightsail get-container-log --service-name x", "cd ops && aws s3 ls",
                        "gh pr merge 46 --merge", "gh secret list", "gh auth token", "gh api repos/o/r/actions/secrets"):
            with self.subTest(command=command):
                self.assertIsNotNone(guard.check(bash(command)))

    def test_other_gh_and_git_commands_are_allowed(self):
        for command in ("gh pr create --fill", "gh pr checks 46", "git status", "gh run view 1 --log-failed"):
            with self.subTest(command=command):
                self.assertIsNone(guard.check(bash(command)))

    def test_adding_secret_or_contract_files_is_blocked(self):
        self.assertIsNotNone(guard.check(bash("git add backend/.env")))
        self.assertIsNotNone(guard.check(bash("git add uploads/acme-msa.pdf && git commit -m x")))
        with mock.patch.object(guard, "staged_files", return_value=["backend/app/main.py"]):
            self.assertIsNone(guard.check(bash("git add backend/app/main.py && git commit -m 'fix'")))

    def test_commit_with_staged_secret_or_contract_files_is_blocked(self):
        with mock.patch.object(guard, "staged_files", return_value=["docs/x.md", "data/contract.docx"]):
            self.assertIn("contract", guard.check(bash("git commit -m 'add'")))
        with mock.patch.object(guard, "staged_files", return_value=[".env"]):
            self.assertIn("secret", guard.check(bash("git commit -m 'add'")))


class ProtocolTest(unittest.TestCase):
    def run_guard(self, payload: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, check=False)

    def test_block_exits_2_with_the_reason_on_stderr(self):
        result = self.run_guard(json.dumps(bash("cat .env")))
        self.assertEqual(result.returncode, 2)
        self.assertIn("docs/permissions.md", result.stderr)

    def test_allow_exits_0_and_bad_input_is_ignored(self):
        self.assertEqual(self.run_guard(json.dumps(bash("ls"))).returncode, 0)
        self.assertEqual(self.run_guard("not json").returncode, 0)


if __name__ == "__main__":
    unittest.main()
