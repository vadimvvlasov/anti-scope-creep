# Agent permissions

What coding agents may do in this repository, what they may not, and what enforces each
rule. The full list of actors and credentials is in
[`security/capability-table.md`](../security/capability-table.md); the pack itself is
described in [agent-extension-pack.md](agent-extension-pack.md).

## The boundary that matters

The local agent (Claude Code) runs in the developer's shell. What keeps production safe
is mostly what is **not** on the machine and what GitHub enforces, not the agent's
instructions:

- Production and dev secrets (database URLs, JWT secret, the deployed Groq key) live only
  in GitHub Environments. The agent never sees them.
- `main` accepts changes only through a pull request with green CI (ruleset, GH-1).
- Deploying to prod needs a reviewer on the `prod` environment; the deploy roles can only
  touch Lightsail services tagged for their environment (SG-2).

## Rules for the local agent

| Rule | Enforced by |
|---|---|
| No AWS CLI | `deny: Bash(aws:*)` in `.claude/settings.json`, and the guard hook for compound commands (`cd x && aws ...`) |
| No merging pull requests, no GitHub secrets or tokens | `deny: Bash(gh pr merge:*)`, `Bash(gh secret:*)`, `Bash(gh auth token:*)`; the hook also stops `gh api .../secrets` |
| Does not read or edit `.env` files or keys in `~/.config/*.env` | `deny: Read(./**/.env)`, `Read(~/.config/*.env)`, `Edit(./**/.env)`; the hook covers `.env.*` variants, private keys and shell reads (`cat`, `grep`, `head`) |
| Does not print the environment | the hook stops `printenv`, a bare `env` and `echo $...KEY/TOKEN/SECRET/PASSWORD` |
| May load a key for an eval run without printing it | `set -a; source ~/.config/gemini.env; set +a` is allowed on purpose |
| Does not commit secrets or uploaded contracts | the hook checks `git add` arguments and the staged files on `git commit` (`.env`, `.pdf`, `.docx`, `.doc`) |
| Works on a feature branch, asks before adding a dependency, keeps `openapi.yaml` in sync | `AGENTS.md`; the `main` ruleset; `tests/test_openapi_contract.py` in CI |
| Pushes branches and opens pull requests | allowed: the developer reviews and merges |

The hook is a guardrail against mistakes, not a sandbox: a determined command can get
around a pattern match. It runs in the same process context as the agent and fails open
on input it does not understand. The credentials that are not on the machine are the
real boundary.

## Subagent

`api-contract-reviewer` gets `Read`, `Grep`, `Glob` and `Bash`. Its instructions limit
Bash to `git diff`, `git log`, `git show` and the contract test; the project hook and
deny rules apply to it as to the main session. It never edits files.

## MCP server

- Read-only: three tools, all annotated `readOnlyHint`; nothing creates, deletes or
  starts an analysis.
- Talks only to a local backend unless `ASC_ALLOW_REMOTE=1` is set, so by default the
  agent sees test data from `make up`, not real users' contracts.
- Uses a test account from `ASC_EMAIL` / `ASC_PASSWORD`; the token stays in memory and is
  not logged. The account sees only its own contracts (the API filters by owner).
- Returns findings (quoted clauses, explanations, suggestions) but never the full
  contract text or the email draft. Quoted clauses still reach the agent's model
  provider, which is why prod data is not the default.
- Tool calls need approval: `.claude/settings.json` allows the three tools by name, and
  `enableAllProjectMcpServers` is off, so the server itself must be approved once.

## Eval keys

Gemini and Groq eval keys are in `~/.config/*.env` on the developer's machine. The agent
may export them into a command's environment to run the eval (the `eval-run` skill), but
not read or print the files. Only public CUAD and synthetic contracts are sent during
eval runs.
