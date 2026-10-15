# anti-scope-creep-agent-pack

Claude Code plugin with the project's agent extension pack:

- skill `eval-run`: plan, run, score, compare and report an eval;
- subagent `api-contract-reviewer`: read-only API change review;
- `PreToolUse` hook `hooks/guard.py`: blocks secret files, printing the environment, the
  AWS CLI, `gh pr merge` / `gh secret`, and committing secrets or contract files;
- MCP server `anti-scope-creep`: read-only tools over the API (needs `uv`, a local
  backend and `ASC_EMAIL` / `ASC_PASSWORD`).

```text
/plugin install anti-scope-creep-agent-pack --marketplace vadimvvlasov/anti-scope-creep
```

The files are copies of the sources in the repository root (`agent-capabilities/`,
`agent-hooks/`, `mcp-server/`), refreshed by `python3 scripts/sync_agent_pack.py` and
checked in CI. Details: [docs/agent-extension-pack.md](../../docs/agent-extension-pack.md),
[docs/permissions.md](../../docs/permissions.md).
