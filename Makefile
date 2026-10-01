.PHONY: install dev-backend dev-frontend test lint

install:
	cd backend && uv sync
	cd frontend && npm i

dev-backend:
	cd backend && uv run uvicorn app.main:create_app --factory --reload

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest
	cd frontend && npm test

lint:
	cd frontend && npm run lint
