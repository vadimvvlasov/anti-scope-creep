# Tests

`make test-all` is the one command for every test (see the README). This page has the steps one by one.

The tests run on the host, so they need [uv](https://docs.astral.sh/uv/) and Node.js 20+
with npm. To run the steps one by one, install the dependencies once (the Docker path
does not):

```bash
make install
make test    # backend (pytest) and frontend (Vitest)
make lint    # ESLint for the frontend
```

End-to-end tests (Playwright, Chromium) drive the real frontend and backend:

```bash
make up
(cd frontend && npm ci && npx playwright install chromium)   # once: Playwright and its browser
# on a fresh Linux machine: npx playwright install --with-deps chromium (also installs system libraries)
make e2e
```

They register fresh users on every run, so they need no seed data. To run them
against another environment, set `E2E_BASE_URL` (frontend) and `E2E_API_URL` (backend).

Backend tests run on SQLite in memory with `make test`. Store, migration and constraint tests also
run on PostgreSQL: `make test-all` does it with a throwaway database, or run `make test-db` and
then `TEST_DATABASE_URL=postgresql+psycopg://postgres:dev@127.0.0.1:5433/asc_test make test`
(`make test-db-down` removes the container). The database name must contain `test`; the tests
wipe it and refuse any other name. See [`backend/README.md`](../backend/README.md).
