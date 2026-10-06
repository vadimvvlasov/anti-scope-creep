"""FastAPI application factory.

Run locally: `uv run uvicorn app.main:create_app --factory --reload`
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.formparsers import MultiPartParser

from app.analyzer import Analyzer, build_analyzer
from app.config import Settings
from app.context import AppContext, Clock, utc_now
from app.errors import register_error_handlers
from app.extraction import MAX_FILE_BYTES
from app.routers import auth, contracts, health, query, version
from app.seed import finish_pending_analyses, seed_demo_data
from app.db import build_engine
from app.store import SqlStore, Store

# Keep uploads up to the size limit in memory instead of spooling them to a temp file:
# the raw binary must never be written anywhere (docs/spec.md "Original uploaded binary").
MultiPartParser.spool_max_size = MAX_FILE_BYTES + 1


def _lifespan(context: AppContext, pending_runs: list[tuple[UUID, UUID]]):
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(finish_pending_analyses(context, pending_runs)) if pending_runs else None
        yield
        if task:
            task.cancel()

    return lifespan


def _sql_store(settings: Settings) -> SqlStore:
    if not settings.database_url:
        raise ValueError("Settings.database_url is required when no store is passed in.")
    return SqlStore(build_engine(settings.database_url))


def create_app(
    settings: Settings | None = None,
    store: Store | None = None,
    analyzer: Analyzer | None = None,
    clock: Clock = utc_now,
) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = settings or Settings.from_env()
    context = AppContext(
        settings=settings,
        store=store or _sql_store(settings),
        analyzer=analyzer or build_analyzer(settings),
        clock=clock,
    )
    pending_runs = seed_demo_data(context) if settings.seed_demo_data else []
    app = FastAPI(
        title="Anti-Scope Creep API", version="0.1.0", lifespan=_lifespan(context, pending_runs)
    )
    app.state.context = context
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    for router in (health.router, version.router, auth.router, contracts.router, query.router):
        app.include_router(router)
    return app
