# Anti-Scope Creep backend

FastAPI implementation of [`openapi.yaml`](../openapi.yaml). Product rules come from
[`docs/spec.md`](../docs/spec.md).

## Run

```bash
uv sync
JWT_SECRET=<long-random-value> uv run uvicorn app.main:create_app --factory --reload
```

The API listens on `http://localhost:8000`. Point the frontend at it with
`VITE_USE_MOCK=false` and `VITE_API_URL=http://localhost:8000`.

Configuration is read from environment variables; see [`.env.example`](.env.example).
The app does not load `.env` files itself, so export the variables or pass them on
the command line.

With `SEED_DEMO_DATA=true` (the default) the in-memory store starts with demo data:

- `demo@example.com` / `password123` — 23 contracts in every status
- `other@example.com` / `password123` — one contract, for checking that other users'
  contracts return `404`

All data lives in memory and is lost on restart.

## Test

```bash
uv run pytest
```

## Layout

| Module | Responsibility |
|---|---|
| `app/main.py` | App factory: settings, store, analyzer, routers, CORS, seeding |
| `app/routers/` | HTTP endpoints, one module per `openapi.yaml` tag |
| `app/models.py` | Domain records (store shape) and Pydantic API schemas |
| `app/store.py` | `Store` interface and the thread-safe `InMemoryStore` |
| `app/auth.py` | Argon2 password hashing, HS256 JWTs, current-user dependency |
| `app/services.py` | Contract use cases: status flow, stale-analysis rule, response mapping |
| `app/extraction.py` | Upload validation, PDF/TXT text extraction, language check |
| `app/analyzer.py` | `Analyzer` interface, validated `AnalysisResult`, deterministic stub |
| `app/runner.py` | `AnalysisRunner` interface, `BackgroundTasks` runner, analysis job |
| `app/errors.py` | Error codes and the `{ "error": { "code", "message" } }` envelope |
| `app/seed.py` | Demo data |
