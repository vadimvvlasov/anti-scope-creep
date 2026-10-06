"""Application settings, read from environment variables."""

import logging
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = ("http://localhost:8080", "http://localhost:5173")
SUPPORTED_ANALYZERS = ("stub", "groq")
# Deployed images carry their tag (sha-<7 hex>) in APP_VERSION; everything else is "local".
DEFAULT_VERSION = "local"


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    database_url: str = ""
    analysis_stale_after_seconds: int = 600
    analyzer: str = "stub"
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    seed_demo_data: bool = True
    version: str = DEFAULT_VERSION
    # Groq (docs/architecture.md, section 4). The key never appears in repr or logs.
    groq_api_key: str = field(default="", repr=False)
    groq_model: str = "openai/gpt-oss-120b"
    groq_tokens_per_minute: int = 8_000
    groq_requests_per_minute: int = 30

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        analyzer = env.get("ANALYZER", "stub")
        if analyzer not in SUPPORTED_ANALYZERS:
            raise ValueError(f"Unsupported ANALYZER {analyzer!r}; expected one of {SUPPORTED_ANALYZERS}")
        if analyzer == "groq" and not env.get("GROQ_API_KEY", "").strip():
            raise ValueError("ANALYZER=groq requires GROQ_API_KEY")
        return cls(
            jwt_secret=_jwt_secret(env),
            database_url=_database_url(env),
            analysis_stale_after_seconds=int(env.get("ANALYSIS_STALE_AFTER_SECONDS", "600")),
            analyzer=analyzer,
            cors_origins=_split_origins(env.get("CORS_ORIGINS")),
            seed_demo_data=_parse_bool(env.get("SEED_DEMO_DATA", "true")),
            version=env.get("APP_VERSION", "").strip() or DEFAULT_VERSION,
            groq_api_key=env.get("GROQ_API_KEY", "").strip(),
            groq_model=env.get("GROQ_MODEL", "").strip() or "openai/gpt-oss-120b",
            groq_tokens_per_minute=int(env.get("GROQ_TOKENS_PER_MINUTE", "8000")),
            groq_requests_per_minute=int(env.get("GROQ_REQUESTS_PER_MINUTE", "30")),
        )


def migrations_database_url(env: Mapping[str, str] = os.environ) -> str:
    """The URL Alembic migrates: MIGRATIONS_DATABASE_URL if set, otherwise DATABASE_URL.

    On Neon the application uses the pooled endpoint (PgBouncer, transaction mode),
    which cannot run migrations; MIGRATIONS_DATABASE_URL points at the direct endpoint.
    """
    return env.get("MIGRATIONS_DATABASE_URL", "").strip() or _database_url(env)


def _database_url(env: Mapping[str, str]) -> str:
    url = env.get("DATABASE_URL", "").strip()
    if not url:
        raise ValueError("DATABASE_URL is not set, e.g. postgresql+psycopg://user:password@localhost:5432/asc")
    return url


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
