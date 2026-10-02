# Anti-Scope Creep backend

FastAPI implementation of [`openapi.yaml`](../openapi.yaml). Product rules come from
[`docs/spec.md`](../docs/spec.md).

## Run

```bash
uv sync
make -C .. db   # local Postgres 16 container `asc-pg` on 127.0.0.1:5432
export DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/asc
uv run alembic upgrade head
JWT_SECRET=<long-random-value> uv run uvicorn app.main:create_app --factory --reload
```

The API listens on `http://localhost:8000`. The frontend calls it by default; set
`VITE_API_URL` to point it elsewhere (or `VITE_USE_MOCK=true` to run without a backend).

Configuration is read from environment variables; see [`.env.example`](.env.example).
The app does not load `.env` files itself, so export the variables or pass them on
the command line.

`DATABASE_URL` is required. The schema comes only from Alembic migrations in
`migrations/`; the app never creates tables. After changing `app/db.py`, add a
migration with `uv run alembic revision --autogenerate -m "<change>"`, review it, and
check that `uv run alembic check` reports no differences.

With `SEED_DEMO_DATA=true` (the default) the first startup on an empty database adds
demo data (later startups find the demo user and skip seeding):

- `demo@example.com` / `password123` — 23 contracts in every status
- `other@example.com` / `password123` — one contract, for checking that other users'
  contracts return `404`

Data is kept in the database across restarts.

## Test

```bash
uv run pytest
```

Tests run on SQLite in memory. Store, migration and constraint tests also run on
PostgreSQL when `TEST_DATABASE_URL` points at a throwaway database (it is wiped):

```bash
docker exec asc-pg psql -U postgres -c "create database asc_test"
TEST_DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/asc_test uv run pytest
```

## Layout

| Module | Responsibility |
|---|---|
| `app/main.py` | App factory: settings, store, analyzer, routers, CORS, seeding |
| `app/routers/` | HTTP endpoints, one module per `openapi.yaml` tag |
| `app/models.py` | Domain records (store shape) and Pydantic API schemas |
| `app/db.py` | SQLAlchemy tables (`users`, `contracts`, `risk_findings`, `email_drafts`), engine |
| `app/store.py` | `Store` interface and `SqlStore` (one transaction per operation) |
| `migrations/` | Alembic environment and migrations; reads `DATABASE_URL` |
| `app/auth.py` | Argon2 password hashing, HS256 JWTs, current-user dependency |
| `app/services.py` | Contract use cases: status flow, stale-analysis rule, response mapping |
| `app/extraction.py` | Upload validation, PDF/TXT text extraction, language check |
| `app/analyzer.py` | `Analyzer` interface, validated `AnalysisResult`, deterministic stub |
| `app/runner.py` | `AnalysisRunner` interface, `BackgroundTasks` runner, analysis job |
| `app/errors.py` | Error codes and the `{ "error": { "code", "message" } }` envelope |
| `app/seed.py` | Demo data |
