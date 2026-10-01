"""Application-wide collaborators, created once per app and shared by requests."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Request

from app.analyzer import Analyzer
from app.config import Settings
from app.store import Store

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    store: Store
    analyzer: Analyzer
    clock: Clock = utc_now


def get_context(request: Request) -> AppContext:
    return request.app.state.context
