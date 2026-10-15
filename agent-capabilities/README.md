# Agent capabilities

Reusable procedures and specialists for coding agents working on this repository. The
files are plain Markdown with Claude Code frontmatter; `.claude/skills/` and
`.claude/agents/` link here, and the plugin under `plugins/` carries copies.

| Path | Kind | Use |
|---|---|---|
| [`eval-run/SKILL.md`](eval-run/SKILL.md) | skill (reusable workflow) | evaluate a prompt, provider, effort or chunking change: plan, run, score, compare, report |
| [`subagents/api-contract-reviewer.md`](subagents/api-contract-reviewer.md) | subagent | read-only review of an API change against the spec, `openapi.yaml`, backend and frontend types |

See [docs/agent-extension-pack.md](../docs/agent-extension-pack.md) for the whole pack.
After editing a file here, run `python3 scripts/sync_agent_pack.py`.
