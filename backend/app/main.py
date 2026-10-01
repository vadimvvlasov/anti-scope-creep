"""FastAPI application factory.

Run locally: `uv run uvicorn app.main:create_app --factory --reload`
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.formparsers import MultiPartParser

from app.analyzer import Analyzer, build_analyzer
from app.config import Settings
from app.context import AppContext, Clock, utc_now
from app.errors import register_error_handlers
from app.extraction import MAX_FILE_BYTES
from app.routers import auth, health
from app.store import InMemoryStore, Store

# Keep uploads up to the size limit in memory instead of spooling them to a temp file:
# the raw binary must never be written anywhere (docs/spec.md "Original uploaded binary").
MultiPartParser.spool_max_size = MAX_FILE_BYTES + 1


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
        store=store or InMemoryStore(),
        analyzer=analyzer or build_analyzer(settings.analyzer),
        clock=clock,
    )
    app = FastAPI(title="Anti-Scope Creep API", version="0.1.0")
    app.state.context = context
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    for router in (health.router, auth.router):
        app.include_router(router)
    return app
