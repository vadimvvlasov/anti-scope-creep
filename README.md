# Anti-Scope Creep

[![CI](https://github.com/vadimvvlasov/anti-scope-creep/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/vadimvvlasov/anti-scope-creep/actions/workflows/ci.yml)

**Live:** https://anti-scope-creep.vadimvlasov.workers.dev (register any email; contracts are analyzed by the Groq LLM analyzer, see the
[AI data policy](docs/ai-data-policy.md))

## Problem

Freelancers and small businesses sign contracts without reading the fine print in
full. Risky clauses hide inside: one-sided termination with no compensation,
unrestricted IP transfer to the client, no cap on liability. Hiring a lawyer for
every contract isn't realistic, and there's rarely time to review one line by line.

## What it does

Anti-Scope Creep reads a contract, flags risky clauses by category (termination,
IP assignment, liability, etc.), and scores each one by risk level (low/medium/
high). It also keeps a searchable history: ask a question about past contracts in
plain English and get an answer without writing SQL.

## How it works for the user

1. Upload a contract (PDF/text) through the web app
2. Get back a list of flagged clauses: category, risk level, the exact quoted text,
   an explanation and a suggested change, plus a draft email to the client. A short
   contract takes seconds; a long one (about 55,000 characters) takes about three
   minutes on the free LLM tier
3. Export the result as a PDF or DOCX report
4. Ask questions about your contract history in natural language (e.g. "which
   contracts this month had uncapped liability?"), and the system translates the
   question into SQL and answers it. Planned: today this screen runs on mock data

## How it's built

Working today:

- An LLM (Groq, `openai/gpt-oss-120b`) reads the contract in chunks and returns
  findings as strict JSON: category, risk level, the quoted clause, an explanation
  and a suggested change, plus a draft email to the client
- Party and signatory names, emails, phone numbers, URLs, bank and tax IDs and
  street addresses are replaced with placeholders before the text leaves the
  backend, and restored in the answer
- Every quote is checked against the contract text; a finding whose quote is not
  there is dropped, so the user can click any finding and see the real clause
- Contracts, analyses and findings are stored in Postgres

Planned:

- History questions through a text-to-SQL agent behind guardrails: read-only
  access, a single SELECT, an enforced row limit
- A small classifier fine-tuned on the CUAD dataset to preselect risky clauses
  before the LLM call, which cuts tokens per contract

## Current status: Phase 3 (LLM analyzer)

The deployed app analyzes real contracts with the Groq LLM analyzer. CI/CD, dev and
prod environments come from Phase 2.

What the app does today:

- React frontend (built in Lovable) with all five screens and a services layer
  (`frontend/src/services/api.ts`) that switches between the real API and an
  in-memory mock with one flag
- FastAPI backend that implements [`openapi.yaml`](openapi.yaml): email/password
  auth with 24-hour JWTs, contract upload (PDF, TXT, pasted text), background
  analysis, findings, client email draft, history with pagination
- PostgreSQL through SQLAlchemy, schema managed by Alembic migrations
- LLM analyzer on Groq (`openai/gpt-oss-120b`) in dev and prod: names and contact
  details are pseudonymized before the call, and a finding whose quote is not in the
  contract is dropped. Locally (`ANALYZER=stub`, the default) a deterministic stub
  returns the fixture findings from [`docs/spec.md`](docs/spec.md)
- Report export as PDF or DOCX: summary, a table of high and medium findings with
  proposed counter-clauses, and the client email
- History Search answers from mock data in mock mode; the real backend returns
  `501` (`History search is coming soon.`) until the text-to-SQL agent phase

Added in Phase 3:

- The Groq analyzer behind `ANALYZER=groq`: chunking, strict structured output,
  a token bucket for the free-tier limits, retries with `retry-after`
- Pseudonymization before every LLM call and quote verification after it
- [AI data policy](docs/ai-data-policy.md) and a notice on the upload screen that
  the contract text goes to a third-party AI provider
- An offline eval with hand-labeled gold sets (CUAD contracts and synthetic
  freelance contracts): precision, recall and severity per category, see
  [`eval/README.md`](eval/README.md). It runs locally; CI never calls the LLM

Added in Phase 2:

- Docker images and `compose.yaml`: `make up` starts the whole system locally
- Playwright end-to-end tests, run in CI against the built stack
- CI on every pull request: backend and frontend tests, e2e, Semgrep, Docker build,
  and a check that `openapi.yaml` matches the routes the backend declares
- Automatic deploy of `main` to a dev environment and a manual, approved promotion
  of the same image to prod (see [Deploy](#deploy))

Not yet: the text-to-SQL agent, the fine-tuned classifier, monitoring.

Product rules live in [`docs/spec.md`](docs/spec.md), infrastructure and phases in
[`docs/architecture.md`](docs/architecture.md).

## AI-assisted development

The project is built spec-first, with AI tools doing most of the typing and a person
deciding, reviewing and verifying. The full process with real prompts is in
[`docs/ai-workflow.md`](docs/ai-workflow.md).

- **Spec first.** The product spec was worked out in a ChatGPT dialogue and saved as
  [`docs/spec.md`](docs/spec.md). It is the source of truth for every later step.
- **Frontend from the spec.** `scripts/build_lovable_prompt.py` turns the spec into a
  Lovable prompt; Lovable generated the React app with a mock services layer.
- **Contract from the frontend.** [`openapi.yaml`](openapi.yaml) was written from the
  frontend's API client, then the FastAPI backend was built against it. A test checks
  that the backend routes match the contract.
- **Backend and infrastructure with Claude Code.** [`AGENTS.md`](AGENTS.md) (read by
  Claude Code through `CLAUDE.md`) and [`frontend/AGENTS.md`](frontend/AGENTS.md) give
  the agent the commands, layout and rules: follow the spec and stop if it is unclear,
  no new dependencies without asking, no secrets in the repository, stay inside the task.
- **One step, one prompt, one pull request.** Each phase is planned as a list of steps.
  Each step gets one prompt, a feature branch and a PR; CI must be green before merge.
- **Human review and verification.** Every step has a checklist: new tests, the full
  suite, a manual check in the browser on dev, the smoke test after deploy. The LLM
  analyzer is checked against gold sets labeled by hand, not by the model.

## Where to find what

Course rubric items and where they live in this repository:

| Item | Where |
|---|---|
| Product spec | [`docs/spec.md`](docs/spec.md) |
| Agent instructions | [`AGENTS.md`](AGENTS.md), [`frontend/AGENTS.md`](frontend/AGENTS.md), `CLAUDE.md` |
| AI-assisted workflow | [AI-assisted development](#ai-assisted-development), [`docs/ai-workflow.md`](docs/ai-workflow.md) |
| Architecture | [`docs/architecture.md`](docs/architecture.md) |
| Frontend and its tests | `frontend/`, `frontend/src/**/__tests__/` |
| API contract | [`openapi.yaml`](openapi.yaml) |
| Backend and its tests | `backend/`, `backend/tests/` |
| Database and migrations | `backend/migrations/`, [Deploy](#deploy) for dev and prod |
| Containers | `backend/Dockerfile`, `frontend/Dockerfile`, [`compose.yaml`](compose.yaml) |
| Integration tests | `frontend/e2e/` (Playwright), [Tests](#tests) |
| Deployment | [Deploy](#deploy) |
| CI/CD | `.github/workflows/`, [Workflows](#workflows) |
| AI data policy | [`docs/ai-data-policy.md`](docs/ai-data-policy.md) |
| LLM eval | [`eval/README.md`](eval/README.md) |

## Screenshots

Screens 1–4 run against the real backend and Postgres; History Search runs on the
mock.

| | |
|---|---|
| ![Login](docs/screenshots/01-login.png) **Login / Register** | ![Contract history](docs/screenshots/02-contract-history.png) **Contract History** |
| ![New analysis](docs/screenshots/03-new-analysis.png) **Upload / Analyze** | ![History search](docs/screenshots/05-history-search.png) **History Search** (mock) |

**Contract Details**: risk summary, findings with the quoted clause, and the client
email draft.

![Contract details](docs/screenshots/04-contract-details.png)

## Run locally

### With Docker (the full system, one command)

You need Docker with Compose.

```bash
make up      # Postgres, migrations, backend, frontend
```

Open http://localhost:3000 and log in as `demo@example.com` / `password123`
(demo accounts are described below). The API is on http://localhost:8000.
`make down` stops everything and keeps the database volume; `make logs` follows the logs.

### For development (hot reload)

You need [uv](https://docs.astral.sh/uv/), Node.js 20+ with npm, and Docker (only
for the Postgres container).

```bash
make install    # backend and frontend dependencies, creates frontend/.env
make db         # Postgres 16 in the container asc-pg on 127.0.0.1:5432
```

Backend, in one terminal. The app does not read `.env` files, so export the
variables (all of them are described in [`backend/.env.example`](backend/.env.example)):

```bash
export DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/asc
export JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
make migrate
make dev-backend    # http://localhost:8000, Swagger UI at /docs
```

Frontend, in another terminal:

```bash
make dev-frontend   # http://localhost:8080
```

Log in as `demo@example.com` / `password123`: the first start on an empty database
seeds 23 demo contracts in every status. `other@example.com` / `password123` owns
one contract, for checking that another user's contract returns `404`.

To run the frontend without a backend, set `VITE_USE_MOCK=true` in `frontend/.env`.

## Deploy

| | Frontend | Backend | Database |
|---|---|---|---|
| **prod** | https://anti-scope-creep.vadimvlasov.workers.dev | https://anti-scope-creep-prod.w7ype86rjt6a6.eu-central-1.cs.amazonlightsail.com | Neon branch `production` |
| **dev** | https://anti-scope-creep-dev.vadimvlasov.workers.dev | Lightsail service `anti-scope-creep-dev`, created on deploy and deleted every night | Neon branch `dev` |

The frontend is static files on Cloudflare Workers. The backend is one container
on an AWS Lightsail container service (`eu-central-1`). The database is Neon
Postgres in the same region. The cloud databases start empty, without demo accounts.
Details and the reasoning behind these choices are in
[`docs/architecture.md`](docs/architecture.md), sections 2, 3 and 7.

### Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | pull requests, pushes to `main` | backend, frontend, e2e, scripts, Semgrep, Docker build |
| `deploy-dev.yml` | CI passed on `main`, or by hand | builds the backend image once (`ghcr.io/vadimvvlasov/anti-scope-creep-backend:sha-<short-sha>`) and deploys it to dev |
| `promote-prod.yml` | by hand, optionally with an image tag | deploys an image that already ran in dev to prod, without a rebuild, after approval |
| `deploy.yml` | called by the two above | runs migrations, deploys to Lightsail, builds and deploys the frontend, runs a smoke test |
| `dev-down.yml` | every night, or by hand | deletes the dev Lightsail service (it is billed until deleted) |

### Promote to prod

1. Wait until `deploy-dev` is green for the commit you want. Its image tag is
   `sha-` plus the first 7 characters of the commit; the dev site shows it in the footer.
2. Actions → **Promote to prod** → Run workflow. Leave the tag empty to promote what the
   last successful `deploy-dev` deployed, or enter one (for example `sha-ce88559`).
   Or: `gh workflow run promote-prod.yml` (`-f image_tag=sha-ce88559` for a specific tag).
3. The first job checks that the tag belongs to a commit on `main` and that the image
   exists, and writes the tag to the run summary. Then the run waits for approval:
   Review deployments → `prod` → Approve.

Migrations run before the new container takes traffic, so they must stay
backward-compatible with the running version.

### Secrets and settings

Everything lives in GitHub Environments `dev` and `prod`, never in the repository.
Both environments accept deployments only from `main`; `prod` also needs a reviewer.

- Secrets: `DATABASE_URL` (Neon pooled endpoint), `MIGRATIONS_DATABASE_URL` (Neon
  direct endpoint, for Alembic), `JWT_SECRET` (different per environment),
  `CLOUDFLARE_API_TOKEN`
- Variables: `AWS_ROLE_ARN`, `AWS_REGION`, `LIGHTSAIL_SERVICE`, `CORS_ORIGINS`,
  `CLOUDFLARE_ACCOUNT_ID`

GitHub Actions reaches AWS only through OIDC roles, one per environment, with no
access keys. The dev role can create, deploy to and delete only services tagged
`env=dev`. The prod role can only deploy to the service tagged `env=prod`.

### Smoke test

`python3 scripts/smoke.py <backend URL>` checks `/health/ready`, registers a new
user, uploads a short contract, waits for the analysis, and deletes the contract.
The deploy workflows run it after every deployment with `--expect-version <tag>`,
so it also fails if `GET /version` reports an older image than the one just deployed.

### Which version runs where

Each deployed image carries its tag in `APP_VERSION` (`sha-<7 hex>`, set at build in
`deploy-dev.yml`). `GET /version` returns it, and the frontend footer shows the same tag.
Local builds show `local`.

### Cleanup

The only paid resource is the prod Lightsail service (Nano, $7 per month). It is
billed until deleted, and the prod role cannot delete it, so delete it by hand:

```bash
aws lightsail delete-container-service --service-name anti-scope-creep-prod --region eu-central-1
```

## Tests

```bash
make test    # backend (pytest) and frontend (Vitest)
make lint    # ESLint for the frontend
```

End-to-end tests (Playwright, Chromium) drive the real frontend and backend:

```bash
make up
(cd frontend && npm ci && npx playwright install chromium)   # once: Playwright and its browser
make e2e
```

They register fresh users on every run, so they need no seed data. To run them
against another environment, set `E2E_BASE_URL` (frontend) and `E2E_API_URL` (backend).

Backend tests run on SQLite in memory. Store, migration and constraint tests also
run on PostgreSQL when `TEST_DATABASE_URL` points at a throwaway database; see
[`backend/README.md`](backend/README.md).

## Commands

Run from the repository root.

| Command | What it does |
|---|---|
| `make install` | Install backend (`uv sync`) and frontend (`npm i`) dependencies |
| `make up` | Build and start the full system in Docker: frontend on `http://localhost:3000`, backend on `http://localhost:8000` |
| `make down` | Stop the compose stack (the database volume is kept) |
| `make logs` | Follow the compose logs |
| `make e2e` | Run the Playwright end-to-end tests against the stack from `make up` |
| `make db` | Start the local Postgres 16 container `asc-pg` |
| `make migrate` | Apply Alembic migrations to `DATABASE_URL` |
| `make dev-backend` | Start the backend dev server on `http://localhost:8000` |
| `make dev-frontend` | Start the frontend dev server on `http://localhost:8080` |
| `make test` | Run backend and frontend tests |
| `make lint` | Lint the frontend with ESLint |
| `python3 scripts/smoke.py <URL>` | Smoke test a deployed backend |
| `python3 -m unittest discover -s scripts` | Run the script tests |

## Repository layout

| Path | Contents |
|---|---|
| `frontend/` | React app (Vite, TanStack Router), services layer and mock API |
| `backend/` | FastAPI app, SQLAlchemy store, Alembic migrations, tests |
| `openapi.yaml` | API contract between frontend and backend |
| `docs/spec.md` | Product specification: screens, API, data model, acceptance criteria |
| `docs/architecture.md` | Hosting, CI/CD, LLM provider, agent layer, phases |
| `docs/ai-data-policy.md` | What contract data goes to the LLM provider and what is kept |
| `docs/ai-workflow.md` | How the project was built with AI tools, with real prompts |
| `docs/screenshots/` | Screenshots used in this README |
| `eval/` | Gold sets and how the LLM analyzer is measured |
| `data/` | Synthetic contracts: pseudonymization fixtures and the base of the freelance eval set |
| `scripts/` | Smoke test and helper scripts (Python standard library only) |
| `.github/workflows/` | CI and deploy workflows |
