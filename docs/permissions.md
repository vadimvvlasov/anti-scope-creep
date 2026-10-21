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

## On-call agent

Runs in GitHub Actions (`.github/workflows/on-call.yml`) when Grafana sends an alert, or by hand.

| Rule | Enforced by |
|---|---|
| Reads Grafana only | `ONCALL_GRAFANA_AUTH` is a read-only token (`metrics:read`, `logs:read`, `traces:read`) |
| Its model never sees a GitHub token | `persist-credentials: false` on checkout; only the publish step gets `GH_TOKEN` |
| Edits only product code and its tests | `write_file` refuses paths outside `backend/app/`, `backend/tests/`, `frontend/src/` and `prompts.py`; `verify` refuses to publish a change that touches anything else |
| Cannot read secrets or workflows | the tools refuse `.git/`, `.github/`, `.env*`, `*.pem`, `*.key` and anything outside the repository |
| Runs only allowlisted commands | tests are `uv run pytest -q -x <target under tests/>`; search is `git grep`; there is no shell tool |
| Never changes `main` directly | it pushes `oncall/<run id>` and opens a pull request; the `main` ruleset requires a pull request with green CI, and a person merges |
| Cannot deploy | no AWS role, no Neon or Cloudflare credentials in the `oncall` environment |
| Its secrets stay with `main` | the `oncall` environment deploys only from `main`, so a workflow edited in a pull request cannot read `GEMINI_API_KEY` |
| Investigates only merged code | the alert's `ref` (the deployed commit) must be a commit sha that is an ancestor of `origin/main`; anything else (a branch name, an unknown commit, a commit only on another branch) fails the run before any secret is used. The agent's own scripts always come from `main`; the commit under investigation is a separate `git worktree` |
| Tests of the repository do not see the credentials | `pytest` runs with the environment of the step minus `GEMINI_*`, `ONCALL_*`, `GH_*`, `GITHUB_TOKEN` and `ACTIONS_*` (`scrubbed_env` in `scripts/oncall_agent.py`, tested) |
| The webhook token cannot push to `main` | the fine-grained token that lets Grafana start the workflow (`repository_dispatch` needs `Contents: write`) is scoped to this repository and expires in 30 days; the `main` ruleset has no bypass, so the token cannot change `main`. It lives only in the Grafana contact point |
| Unsure means a person decides | `needs_human`, a failed check or no verdict becomes an issue labelled `needs-human-review` |

The model is Gemini on the free tier. It receives the alert context (counts, codes, ids, log
messages and span names of the service, which hold no contract text by design and by test,
`backend/tests/test_telemetry_signals.py`) and files of this public repository. What it writes is
posted publicly, so the prompt forbids copying log lines, personal data or keys into it.

## Eval keys

Gemini and Groq eval keys are in `~/.config/*.env` on the developer's machine. The agent
may export them into a command's environment to run the eval (the `eval-run` skill), but
not read or print the files. Only public CUAD and synthetic contracts are sent during
eval runs.
