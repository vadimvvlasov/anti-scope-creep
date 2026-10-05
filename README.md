# Anti-Scope Creep

[![CI](https://github.com/vadimvvlasov/anti-scope-creep/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/vadimvvlasov/anti-scope-creep/actions/workflows/ci.yml)

**Live:** https://anti-scope-creep.vadimvlasov.workers.dev (register any email; the analyzer is still the stub, see below)

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
2. Get back a list of flagged clauses in seconds — category, risk level, and the
   exact quoted text
3. Ask questions about your contract history in natural language (e.g. "which
   contracts this month had uncapped liability?") — the system translates the
   question into SQL and answers it

## How it's built (target design)

- An LLM extracts risky clauses from the contract text
- A small fine-tuned classifier (trained on real legal data — the CUAD dataset)
  scores each clause's risk category — cheaper and faster than calling a large
  LLM per clause
- Findings are stored in Postgres
- History questions go through a dedicated text-to-SQL agent, sandboxed behind
  guardrails: read-only access, single SELECT only, enforced row limit — so the
  agent can't modify data or return unbounded results

## Current status: Phase 2 (deployed MVP)

The Phase 1 slice now runs in the cloud, with CI/CD around it.

What the app does today:

- React frontend (built in Lovable) with all five screens and a services layer
  (`frontend/src/services/api.ts`) that switches between the real API and an
  in-memory mock with one flag
- FastAPI backend that implements [`openapi.yaml`](openapi.yaml): email/password
  auth with 24-hour JWTs, contract upload (PDF, TXT, pasted text), background
  analysis, findings, client email draft, history with pagination
- PostgreSQL through SQLAlchemy, schema managed by Alembic migrations
- Deterministic stub analyzer: every contract gets the same fixture findings from
  [`docs/spec.md`](docs/spec.md). The LLM analyzer and the risk classifier replace
  it in later phases
- History Search answers from mock data in mock mode; the real backend returns
  `501` (`History search is coming soon.`) until the text-to-SQL agent phase

Added in Phase 2:

- Docker images and `compose.yaml`: `make up` starts the whole system locally
- Playwright end-to-end tests, run in CI against the built stack
- CI on every pull request: backend and frontend tests, e2e, Semgrep, Docker build,
  and a check that `openapi.yaml` matches the routes the backend declares
- Automatic deploy of `main` to a dev environment and a manual, approved promotion
  of the same image to prod (see [Deploy](#deploy))

Not yet: the LLM analyzer, the fine-tuned classifier, the text-to-SQL agent,
monitoring.

Product rules live in [`docs/spec.md`](docs/spec.md), infrastructure and phases in
[`docs/architecture.md`](docs/architecture.md).

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
| `promote-prod.yml` | by hand, with an image tag | deploys an image that already ran in dev to prod, without a rebuild, after approval |
| `deploy.yml` | called by the two above | runs migrations, deploys to Lightsail, builds and deploys the frontend, runs a smoke test |
| `dev-down.yml` | every night, or by hand | deletes the dev Lightsail service (it is billed until deleted) |

### Promote to prod

1. Wait until `deploy-dev` is green for the commit you want. Its image tag is
   `sha-` plus the first 7 characters of the commit.
2. Actions → **Promote to prod** → Run workflow, enter the tag (for example
   `sha-ce88559`). Or: `gh workflow run promote-prod.yml -f image_tag=sha-ce88559`.
3. The first job checks that the tag belongs to a commit on `main` and that the image
   exists. Then the run waits for approval: Review deployments → `prod` → Approve.

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
The deploy workflows run it after every deployment.

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
| `docs/screenshots/` | Screenshots used in this README |
| `scripts/` | Smoke test and helper scripts (Python standard library only) |
| `.github/workflows/` | CI and deploy workflows |
