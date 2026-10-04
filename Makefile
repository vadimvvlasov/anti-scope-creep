.PHONY: install up down logs e2e db migrate dev-backend dev-frontend test lint

install:
	cd backend && uv sync
	cd frontend && npm i
	cd frontend && (test -f .env || cp .env.example .env)

# The full system in Docker (compose.yaml): frontend on http://localhost:3000.
up:
	docker compose up -d --build --wait

down:
	docker compose down

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

lint:
	cd frontend && npm run lint
