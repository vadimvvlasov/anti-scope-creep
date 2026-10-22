# AGENTS.md

Anti-Scope Creep: a web app that flags risky clauses in freelance contracts,
scores them, and drafts an email to the client.

## Source of truth

- `docs/spec.md` is the product specification. Follow it exactly: data model,
  validation limits, status flow, severity matrix, error codes.
- If the spec is unclear or contradicts itself, stop and ask. Do not invent behavior.
- Do not edit `docs/spec.md` without asking.
- `openapi.yaml` is the API contract between frontend and backend.
  The backend implements it; do not change it silently.

## Process and team (read before starting a task)

- Tasks live in GitHub Issues, each with acceptance criteria; one task is one branch and one pull
  request that says `Closes #<n>`. How: `docs/ai-workflow.md`, section "Tracker".
- Who the agents are, what each may touch and how work passes between them:
  `docs/ai-workflow.md`, section "Agent team". What each may and may not do, and what enforces it:
  `docs/permissions.md`.
- Architecture, CI/CD, observability and the on-call agent: `docs/architecture.md`. Operations:
  `ops/runbook.md`.

## Repository layout

- `backend/` - FastAPI app and its tests
- `frontend/` - React + TypeScript app (exported from Lovable)
- `docs/` - specification, architecture, workflow, permissions, deploy, testing, rubric coverage
- `openapi.yaml` - API contract
- `ops/` - runbook, Grafana dashboard and alert rules, the on-call prompt, diagnoses
- `eval/`, `data/` - gold sets, runs and synthetic contracts for the LLM eval
- `security/` - scanner, audit and model-review runs with a decision per finding
- `scripts/` - smoke test and helper scripts (standard library only)
- `agent-capabilities/`, `agent-hooks/`, `mcp-server/`, `plugins/`, `.claude/` - the agent extension pack

## Commands

Makefile (run from the repository root):

- `make install` - install backend (`uv sync`) and frontend (`npm i`) dependencies
- `make up` - build and start the full system in Docker (`compose.yaml`): Postgres, migrations,
  backend on `http://localhost:8000`, frontend on `http://localhost:3000`
- `make down` - stop it (the database volume is kept)
- `make logs` - follow the compose logs
- `make e2e` - run the Playwright end-to-end tests (`frontend/e2e/*.e2e.ts`) against the stack from `make up`
- `make db` - start the local Postgres 16 container `asc-pg` on `127.0.0.1:5432`
- `make migrate` - apply Alembic migrations to `DATABASE_URL`
- `make dev-backend` - start the backend dev server on `http://localhost:8000`
- `make dev-frontend` - start the frontend dev server
- `make test` - run backend and frontend tests
- `make test-all` - all tests in one command: `make test`, then the Docker stack and `make e2e`, then stop the stack
- `make lint` - lint the frontend with ESLint (the backend has no linter configured)

Backend (use uv for dependency management):

- `uv sync` - install dependencies
- `uv add <PACKAGE-NAME>` - add a dependency
- `uv run pytest` - run the whole test suite
- `uv run pytest tests/test_<module>.py` - run one test file
- `uv run python <PYTHON-FILE>` - run a script
- `uv run alembic upgrade head` - apply migrations to `DATABASE_URL`
- `uv run alembic revision --autogenerate -m "<change>"` - draft a migration (review it before committing)
- `TEST_DATABASE_URL=<throwaway-postgres-url> uv run pytest` - also run database tests on PostgreSQL
- `GROQ_API_KEY=<key> uv run python -m evaluation run --run <name> [--set freelance|cuad] [--limit N]` - run the Groq analyzer over the eval gold sets; results are cached in `eval/runs/<name>/`, and a rerun skips cached contracts (local only, never in CI)
- `GEMINI_API_KEY=<key> uv run python -m evaluation run --run <name> --provider gemini [--chunk-chars N] [--max-output-tokens N]` - the same analyzer on Gemini (`GEMINI_MODEL`, default `gemini-3.5-flash-lite`) through its OpenAI-compatible endpoint; `--chunk-chars 60000` sends a contract in one request
- `uv run python -m evaluation score --run <name> [--set freelance|cuad]` - compute precision, recall and severity accuracy from the cache, no tokens

Frontend:

- `npm i` - install dependencies
- `npm run dev` - start the dev server
- `npm test` - run frontend tests

Scripts (Python standard library only):

- `python3 scripts/build_lovable_prompt.py -o <FILE>` - build the Lovable prompt from `docs/spec.md`
- `python3 -m unittest discover -s scripts` - run script tests
- `python3 scripts/smoke.py <BACKEND-URL> [--expect-version sha-<7 hex>]` - smoke test a deployed backend (health, version, register, upload, poll, delete)
- `python3 scripts/select_cuad.py --download`, then `python3 scripts/select_cuad.py -o eval/gold/cuad.draft.jsonl` - pick the CUAD eval subset and write draft gold records (see `eval/README.md`)
- `python3 scripts/build_freelance_set.py` - build the freelance eval set (mutated synthetic contracts) and its gold records (see `eval/README.md`)

Agent extension pack (see `docs/agent-extension-pack.md`):

- `python3 -m unittest discover -s agent-hooks` - test the guard hook
- `cd mcp-server && uv run python -m unittest` - test the MCP server
- `python3 scripts/sync_agent_pack.py` - refresh the plugin copies after editing
  `agent-capabilities/`, `agent-hooks/guard.py` or `mcp-server/`

## Workflow

- Before changing code, create a feature branch (`git checkout -b feat/<short-description>`).
  Never commit directly to `main`.
- Commit regularly, in small commits with clear messages.
- Write tests for new behavior. The whole suite must pass before you commit.

## Rules

- Do not add a dependency without asking first.
- Follow SOLID; keep functions under 50 lines.
- Never commit secrets. Configuration goes through environment variables;
  keep a `.env.example` with placeholder values.
- Never return password hashes or other users' data from the API.
  A contract that belongs to another user returns 404, not 403 (see spec).
- Stay inside the task. If you notice something out of scope, mention it
  instead of fixing it.

## Security boundaries

- Do not run the AWS CLI, merge pull requests, or touch GitHub secrets or tokens:
  deploys and merges are the developer's. `.claude/settings.json` denies these and
  `agent-hooks/guard.py` blocks them.
- Do not read, print or edit `.env` files or keys in `~/.config/*.env`. To run the eval,
  load a key with `set -a; source <file>; set +a` without printing it.
- Never commit uploaded contracts (`.pdf`, `.docx`) or secrets.
- The MCP server is read-only and talks to the local stack by default; do not point it
  at prod data. Details: `docs/permissions.md`.
