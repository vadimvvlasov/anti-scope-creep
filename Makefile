.PHONY: install up up-observability down logs e2e db migrate dev-backend dev-frontend test test-db test-db-down test-all lint

install:
	cd backend && uv sync
	cd frontend && npm i
	cd frontend && (test -f .env || cp .env.example .env)

# The full system in Docker (compose.yaml): frontend on http://localhost:3000.
up:
	docker compose up -d --build --wait

# `make up` plus the local Grafana stack (http://localhost:3001); the backend exports to it.
up-observability:
	OTEL_EXPORTER_OTLP_ENDPOINT=http://lgtm:4318 docker compose --profile observability up -d --build --wait

down:
	docker compose --profile observability down

logs:
	docker compose logs -f

# Playwright end-to-end tests against the running stack (run `make up` first).
e2e:
	cd frontend && npm run e2e

# Only Postgres, for running the backend and tests on the host (make dev-backend).
db:
	docker start asc-pg 2>/dev/null || docker run --name asc-pg -e POSTGRES_PASSWORD=dev \
		-e POSTGRES_DB=asc -p 127.0.0.1:5432:5432 -d postgres:16

# Needs DATABASE_URL in the environment (see backend/.env.example).
migrate:
	cd backend && uv run alembic upgrade head

dev-backend:
	cd backend && uv run uvicorn app.main:create_app --factory --reload

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest
	cd frontend && npm test

# A throwaway PostgreSQL for the database tests: its own container and port, database `asc_test`,
# never the database of `make db` or `make up`. The tests wipe it.
TEST_PG_PORT ?= 5433
TEST_PG_URL = postgresql+psycopg://postgres:dev@127.0.0.1:$(TEST_PG_PORT)/asc_test

test-db:
	docker rm -f asc-pg-test >/dev/null 2>&1 || true
	docker run --name asc-pg-test -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=asc_test \
		-p 127.0.0.1:$(TEST_PG_PORT):5432 -d postgres:16
	until docker exec asc-pg-test pg_isready -U postgres -d asc_test >/dev/null 2>&1; do sleep 1; done

test-db-down:
	docker rm -f asc-pg-test

# Every test with one command from a fresh clone: the unit tests (the store, migration and
# constraint tests also on PostgreSQL), then the full system in Docker and the Playwright
# end-to-end tests against it. The test database and the stack are stopped afterwards, also
# when a test fails, and the exit status of the tests is kept. On a fresh Linux machine
# run `cd frontend && npx playwright install --with-deps chromium` once first (system libraries).
test-all: install
	status=0; \
	$(MAKE) test-db && TEST_DATABASE_URL=$(TEST_PG_URL) $(MAKE) test \
		&& $(MAKE) up && (cd frontend && npx playwright install chromium) && $(MAKE) e2e || status=$$?; \
	$(MAKE) down; $(MAKE) test-db-down; exit $$status

lint:
	cd frontend && npm run lint
