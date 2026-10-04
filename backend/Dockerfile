# syntax=docker/dockerfile:1
# Backend image for local compose and AWS Lightsail. Build from backend/: `docker build -t asc-backend .`

FROM python:3.12-slim-bookworm AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

COPY --from=ghcr.io/astral-sh/uv:0.9.22 /uv /bin/uv

WORKDIR /app

# Locked runtime dependencies only, in their own layer for caching.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app


FROM python:3.12-slim-bookworm

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
# Root-owned and read-only for the app user: the container writes nothing to disk.
COPY --from=build /app /app

USER app
EXPOSE 8000

# Migrations are not run here; deploy jobs run `alembic upgrade head` with this image.
# The port can be overridden with PORT (default 8000); uvicorn does not read it, so the shell does.
CMD ["sh", "-c", "exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
