# Capability table

Every agent, service and workflow that can act on this project: what it can do, which
credentials it holds, and what stops it. A model supplies confidence; code and
configuration outside the model enforce permission. Checked on 2026-10-12.

| Actor | Can do | Credentials | Cannot do / guarded by | Findings |
|---|---|---|---|---|
| Claude Code (local coding agent) | read and edit the working tree, run shell commands (uv, npm, docker, git, gh), run the eval | inherits the developer's shell: `gh` login (push branches, open PRs), AWS CLI profile of an IAM user, eval keys in `~/.config/*.env` when exported | GitHub Environment secrets (database URLs, JWT secret, the deployed Groq key) are not on the machine. Every command goes through Claude Code permission prompts; `AGENTS.md` forbids committing to `main`, adding dependencies without asking and committing secrets; the `main` ruleset (GH-1) requires a pull request with green CI | AG-1, GH-1 |
| Lovable (frontend generator) | generated the frontend in its own project; the code was exported and copied into `frontend/` | none in this repository: all commits here are by the developer | Lovable does not push to this repository. Whether its GitHub App still has access to it is checked in GitHub Settings → Integrations (not visible through the API token). The `LOVABLE` block in `frontend/AGENTS.md` came with the export | none |
| CI (`ci.yml`) | build and test on pull requests and pushes to `main`, Semgrep, e2e on a local stack | `GITHUB_TOKEN` with `contents: read`; no deploy secrets | all actions pinned to a commit SHA (SG-1) | SG-1 |
| `deploy-dev.yml` | build the backend image, deploy it to dev | OIDC role for dev; the five dev secrets passed by name | the dev role can create, deploy to and delete only Lightsail services tagged `env=dev`; the `dev` environment accepts deployments only from `main` | SG-2 |
| `promote-prod.yml` | deploy an image that already ran in dev to prod | OIDC role for prod; the five prod secrets passed by name | the `prod` environment requires a reviewer and accepts only `main`; the prod role can only deploy to the service tagged `env=prod`, not delete it | SG-2 |
| Backend (runtime) | read and write its Postgres database, call Groq | `DATABASE_URL`, `JWT_SECRET`, `GROQ_API_KEY` from environment variables | the key is never logged or shown in `repr`; only pseudonymized text goes to Groq; every user-facing query filters by owner | MR-1 to MR-6 |
| Groq (LLM provider) | receives pseudonymized contract chunks and returns findings | none on our side | Zero Data Retention enabled for the organization; output validated by a strict JSON schema, Pydantic and quote verification ([AI data policy](../docs/ai-data-policy.md)) | MR-3 |
| Gemini (eval only) | receives public CUAD and synthetic contracts during local eval runs | a developer key in `~/.config/gemini.env` | never configured in dev or prod; the free tier forbids confidential data, so only public and synthetic contracts are sent | none |

## Planned with the agent extension pack

The MCP server, subagent, skill and hook added for the course rubric get their own rows
here, together with the permission rules from AG-1: deny `aws` and `gh` merge and secret
commands for the agent, and a hook that blocks reading `.env` files and committing
contract text.
