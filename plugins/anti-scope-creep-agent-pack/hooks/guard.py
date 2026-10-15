#!/usr/bin/env python3
"""PreToolUse guard for coding agents (Claude Code hook protocol, standard library only).

Reads the tool call as JSON on stdin. Exit 0 lets it run; exit 2 blocks it and the
message on stderr goes back to the agent. Blocks:

- reading or editing secret files: `.env` files (not `.env.example`), keys in
  `~/.config/*.env`, private keys;
- shell commands that print secrets: reading those files, `printenv`, a bare `env`,
  echoing a variable named like a key or token;
- commands that hold credentials the agent must not use (AG-1): the AWS CLI, `gh pr merge`,
  `gh secret`, `gh auth token`, GitHub secrets through `gh api`;
- `git add` of, or `git commit` with staged, secret files or uploaded contract files
  (`.pdf`, `.docx`, `.doc`).

This is a guardrail against mistakes, not a sandbox: a determined command can get around
a pattern match. Permissions in `.claude/settings.json` and the credentials that are not
on the machine at all are the real boundary (docs/permissions.md).
"""

import json
import re
import subprocess
import sys
from pathlib import PurePath

SECRET_FILE = re.compile(r"(^|/)\.env(\.[\w-]+)?$|(^|/)\.config/[\w.-]+\.env$|(^|/)id_(rsa|ed25519)$|\.pem$")
SAFE_FILE = re.compile(r"(^|/)\.env\.example$")
# A secret file named anywhere in a shell command.
SECRET_IN_COMMAND = re.compile(r"(?<![\w.-])(?:\S*/)?\.env(?:\.(?!example\b)[\w-]+)?(?![\w.-])|\.config/[\w.-]+\.env\b")
# Loading a key into the environment without printing it is allowed (the eval needs it).
LOAD_ONLY = re.compile(r"^\s*(?:set -a;?\s*)?(?:source|\.)\s+\S+\s*(?:;\s*set \+a)?\s*$")
PRINTS_ENV = re.compile(r"(?:^|[;&|(]\s*)(?:printenv\b|env\s*(?:$|[;&|)]))|\becho\b[^;&|]*\$\{?\w*(?:KEY|TOKEN|SECRET|PASSWORD)", re.I)
FORBIDDEN = (
    (re.compile(r"(?:^|[;&|(`]\s*|\$\(\s*)aws\s"), "the AWS CLI is reserved for the developer (AG-1)"),
    (re.compile(r"\bgh\s+pr\s+merge\b"), "merging pull requests is reserved for the developer (AG-1)"),
    (re.compile(r"\bgh\s+secret\b|\bgh\s+auth\s+token\b|\bgh\s+api\b[^;&|]*secrets"), "GitHub secrets and tokens are off limits (AG-1)"),
)
CONTRACT_FILE = re.compile(r"\.(pdf|docx?)$", re.I)


def check(call: dict) -> str | None:
    """The reason to block this tool call, or None to allow it."""
    tool, args = call.get("tool_name", ""), call.get("tool_input") or {}
    if tool == "Bash":
        return check_command(str(args.get("command", "")))
    for key in ("file_path", "path", "notebook_path"):
        if key in args and is_secret_file(str(args[key])):
            return f"{args[key]} holds secrets; agents do not read or edit it"
    return None


def is_secret_file(path: str) -> bool:
    path = PurePath(path).as_posix()
    return bool(SECRET_FILE.search(path)) and not SAFE_FILE.search(path)


def check_command(command: str) -> str | None:
    for pattern, reason in FORBIDDEN:
        if pattern.search(command):
            return reason
    if PRINTS_ENV.search(command):
        return "this command can print secrets from the environment"
    for part in re.split(r"&&|\|\||;|\n", command):
        if SECRET_IN_COMMAND.search(part) and not LOAD_ONLY.match(part):
            return "this command reads a secret file; load it with `set -a; source <file>; set +a` instead"
    added = re.search(r"\bgit\s+add\b([^;&|]*)", command)
    if added:
        reason = check_staged(added.group(1).split())
        if reason:
            return reason.replace("staged", "adding", 1)
    if re.search(r"\bgit\s+commit\b", command):
        return check_staged(staged_files())
    return None


def check_staged(files: list[str]) -> str | None:
    secrets = [f for f in files if is_secret_file(f)]
    contracts = [f for f in files if CONTRACT_FILE.search(f)]
    if secrets:
        return f"staged secret files: {', '.join(secrets)}"
    if contracts:
        return f"staged contract files (uploads stay out of git): {', '.join(contracts)}"
    return None


def staged_files() -> list[str]:
    result = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=False)
    return result.stdout.split()


def main() -> int:
    try:
        call = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # not a tool call this hook understands
    reason = check(call)
    if reason:
        print(f"Blocked by agent-hooks/guard.py: {reason}. See docs/permissions.md.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
