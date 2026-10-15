# Agent hooks

[`guard.py`](guard.py) is a `PreToolUse` hook (Claude Code hook protocol, Python standard
library only). It blocks a tool call by exiting with code 2; the reason on stderr goes
back to the agent.

Blocked: reading or editing secret files (`.env`, `.env.*` except `.env.example`,
`~/.config/*.env`, private keys), printing the environment, the AWS CLI, `gh pr merge`,
`gh secret`, `gh auth token`, and `git add` or `git commit` of secrets or contract files
(`.pdf`, `.docx`, `.doc`). Loading a key with `set -a; source <file>; set +a` is allowed.

Wired in [`.claude/settings.json`](../.claude/settings.json) for every Bash and file tool.
Rationale and limits: [docs/permissions.md](../docs/permissions.md).

```bash
python3 -m unittest discover -s agent-hooks
echo '{"tool_name":"Bash","tool_input":{"command":"cat .env"}}' | python3 agent-hooks/guard.py; echo $?   # 2
```

After editing `guard.py`, run `python3 scripts/sync_agent_pack.py`.
