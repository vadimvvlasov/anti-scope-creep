"""Application settings, read from environment variables."""

import logging
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = ("http://localhost:8080", "http://localhost:5173")
SUPPORTED_ANALYZERS = ("stub",)


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    analysis_stale_after_seconds: int = 600
    analyzer: str = "stub"
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    seed_demo_data: bool = True

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        analyzer = env.get("ANALYZER", "stub")
        if analyzer not in SUPPORTED_ANALYZERS:
            raise ValueError(f"Unsupported ANALYZER {analyzer!r}; expected one of {SUPPORTED_ANALYZERS}")
        return cls(
            jwt_secret=_jwt_secret(env),
            analysis_stale_after_seconds=int(env.get("ANALYSIS_STALE_AFTER_SECONDS", "600")),
            analyzer=analyzer,
            cors_origins=_split_origins(env.get("CORS_ORIGINS")),
            seed_demo_data=_parse_bool(env.get("SEED_DEMO_DATA", "true")),
        )


def _jwt_secret(env: Mapping[str, str]) -> str:
    secret = env.get("JWT_SECRET", "")
    if secret:
        if len(secret.encode()) < 32:
            logger.warning("JWT_SECRET is shorter than 32 bytes; use a longer random value.")
        return secret
    logger.warning("JWT_SECRET is not set; using a random secret. Tokens will not survive a restart.")
    return secrets.token_urlsafe(32)


def _split_origins(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return DEFAULT_CORS_ORIGINS
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}
