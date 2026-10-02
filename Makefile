.PHONY: install db migrate dev-backend dev-frontend test lint

install:
	cd backend && uv sync
	cd frontend && npm i
	cd frontend && (test -f .env || cp .env.example .env)

# Local Postgres 16 in one container (not the app's compose file, that is Phase 2).
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
