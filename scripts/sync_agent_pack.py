"""Copy the agent extension pack sources into the Claude Code plugin folder.

The sources live where the course rubric expects them (agent-capabilities/, agent-hooks/,
mcp-server/); the plugin under plugins/ needs its own copies, because an installed plugin
is copied out of the repository. Run after changing a source:

    python3 scripts/sync_agent_pack.py

scripts/test_sync_agent_pack.py fails in CI when a copy is out of date.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "anti-scope-creep-agent-pack"
COPIES = {
    "agent-capabilities/eval-run/SKILL.md": "skills/eval-run/SKILL.md",
    "agent-capabilities/subagents/api-contract-reviewer.md": "agents/api-contract-reviewer.md",
    "agent-hooks/guard.py": "hooks/guard.py",
    "mcp-server/server.py": "mcp-server/server.py",
    "mcp-server/pyproject.toml": "mcp-server/pyproject.toml",
    "mcp-server/uv.lock": "mcp-server/uv.lock",
}


def main() -> None:
    for source, target in COPIES.items():
        destination = PLUGIN / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, destination)
        print(f"{source} -> {destination.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
