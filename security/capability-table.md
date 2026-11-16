# Capability table

Every agent, service and workflow that can act on this project: what it can do, which
credentials it holds, and what stops it. A model supplies confidence; code and
configuration outside the model enforce permission. Checked on 2026-10-12; the deploy rows and the server
updated on 2026-11-16, after the backend moved from AWS Lightsail to a home server.

| Actor | Can do | Credentials | Cannot do / guarded by | Findings |
|---|---|---|---|---|
| Claude Code (local coding agent) | read and edit the working tree, run shell commands (uv, npm, docker, git, gh), run the eval | inherits the developer's shell: `gh` login (push branches, open PRs), the developer's SSH key to the home server (an account with `sudo`), eval keys in `~/.config/*.env` when exported | `.claude/settings.json` denies `aws`, `gh pr merge`, `gh secret`, `gh auth token` and reading `.env` files; the `agent-hooks/guard.py` hook also blocks compound forms, printing the environment and committing secrets or contract files ([permissions](../docs/permissions.md)). GitHub Environment secrets are not on the machine; the `main` ruleset (GH-1) requires a pull request with green CI | AG-1 (fixed), GH-1 |
| Lovable (frontend generator) | generated the frontend in its own project; the code was exported and copied into `frontend/` | none in this repository: all commits here are by the developer | Lovable does not push to this repository. Whether its GitHub App still has access to it is checked in GitHub Settings → Integrations (not visible through the API token). The `LOVABLE` block in `frontend/AGENTS.md` came with the export | none |
| CI (`ci.yml`) | build and test on pull requests and pushes to `main`, Semgrep, e2e on a local stack | `GITHUB_TOKEN` with `contents: read`; no deploy secrets | all actions pinned to a commit SHA (SG-1) | SG-1 |
| `deploy-dev.yml` | build the backend image, migrate the Neon dev branch, move the `:dev` tag, deploy the dev frontend | `GITHUB_TOKEN` with `packages: write`; `MIGRATIONS_DATABASE_URL` and `CLOUDFLARE_API_TOKEN` of `dev`, passed by name | no credentials for the server: it only moves a tag that the server pulls; the `dev` environment accepts deployments only from `main` | SG-2 (AWS roles, gone with AWS) |
| `promote-prod.yml` | move `:prod` to an image that already ran in dev, migrate the Neon production branch, deploy the prod frontend | the same, from `prod` | the `prod` environment requires a reviewer and accepts only `main`; the tag must be a `sha-*` of a commit on `main` that exists in ghcr | SG-2 (as above) |
| Home server (`asc-pull.timer`) | pull `:dev` and `:prod` from ghcr every 5 minutes and restart what changed | none for ghcr (public package); the runtime env files, mode 600, owned by `asc` | containers read-only with all capabilities dropped and no Docker socket; blocked from the home LAN (`DOCKER-USER`); public only through its own Tailscale node with Funnel, which the policy file gives no access to other nodes ([self-host](../docs/self-host.md)) | none |
| Backend (runtime) | read and write its Postgres database, call Groq | `DATABASE_URL`, `JWT_SECRET`, `GROQ_API_KEY` from the server's env file of its environment | the key is never logged or shown in `repr`; only pseudonymized text goes to Groq; every user-facing query filters by owner | MR-1 to MR-6 |
| Groq (LLM provider) | receives pseudonymized contract chunks and returns findings | none on our side | Zero Data Retention enabled for the organization; output validated by a strict JSON schema, Pydantic and quote verification ([AI data policy](../docs/ai-data-policy.md)) | MR-3 |
| Gemini (eval only) | receives public CUAD and synthetic contracts during local eval runs | a developer key in `~/.config/gemini.env` | never configured in dev or prod; the free tier forbids confidential data, so only public and synthetic contracts are sent | none |

## Agent extension pack

| Actor | Can do | Credentials | Cannot do / guarded by | Findings |
|---|---|---|---|---|
| `api-contract-reviewer` subagent | read files, `git diff`/`log`/`show`, the OpenAPI contract test | the main session's | instructed not to edit or change state; the project deny rules and guard hook apply to it | none |
| `eval-run` skill | run the eval, which calls Groq or Gemini with public and synthetic contracts | eval keys loaded into the command's environment | keys are loaded with `source`, never read or printed (guard hook); no prompt tuning on held-out | none |
| MCP server (`mcp-server/`) | read service status, the test account's contract list and findings | `ASC_EMAIL` / `ASC_PASSWORD` of a test account; the token stays in memory | read-only tools; local backend only unless `ASC_ALLOW_REMOTE=1`; never returns the full contract text or the email draft; tool calls need approval | none |
| Guard hook (`agent-hooks/guard.py`) | block a tool call | none | a pattern match, not a sandbox: it stops mistakes, not a determined command | AG-1 |
