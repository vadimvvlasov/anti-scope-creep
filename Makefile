.PHONY: install up up-observability down logs e2e db migrate dev-backend dev-frontend test test-all lint

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

# Every test with one command from a fresh clone: the unit tests, then the full system in
# Docker and the Playwright end-to-end tests against it. The stack is stopped afterwards,
# also when a test fails, and the exit status of the tests is kept. On a fresh Linux machine
# run `cd frontend && npx playwright install --with-deps chromium` once first (system libraries).
test-all: install test
	status=0; \
	$(MAKE) up && (cd frontend && npx playwright install chromium) && $(MAKE) e2e || status=$$?; \
	$(MAKE) down; exit $$status

lint:
	cd frontend && npm run lint
