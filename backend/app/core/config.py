"""Application configuration.

Single source of truth for runtime settings. Everything is overridable through
environment variables (or a local ``.env`` file), so the same image runs in the
sandbox (fixture data, in-memory cache) and in production (live OpenF1,
Postgres + Redis) with no code changes.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PITWALL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General -----------------------------------------------------------
    app_name: str = "Pit Wall"
    environment: Literal["dev", "prod", "test"] = "dev"
    log_level: str = "INFO"

    # --- Data source -------------------------------------------------------
    # "openf1"  -> hit the live OpenF1 REST API (needs network egress)
    # "fixture" -> serve a bundled sample session (works fully offline)
    data_source: Literal["openf1", "fixture"] = "fixture"
    openf1_base_url: str = "https://api.openf1.org/v1"
    openf1_timeout_s: float = 15.0
    # OpenF1 free tier is rate limited; keep concurrent fan-out modest.
    openf1_max_concurrency: int = 4

    # --- Cache (Redis, optional) ------------------------------------------
    # When unreachable the app transparently falls back to an in-process LRU.
    redis_url: str | None = Field(default=None)
    cache_ttl_s: int = 30          # live-ish data
    cache_ttl_static_s: int = 3600  # immutable replay data / geometry

    # --- Database (Postgres, optional) ------------------------------------
    # When unset the app runs without persistence (nothing is stored, but all
    # endpoints still work by serving straight from the source + cache).
    database_url: str | None = Field(default=None)

    # --- HTTP / CORS -------------------------------------------------------
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    serve_frontend: bool = True

    # --- Data-loading discipline (see TZ §5) ------------------------------
    location_hz: float = 3.0   # target sample rate for map coordinates
    telemetry_window_s: int = 30  # default sliding window for car_data

    @model_validator(mode="after")
    def _resolve_infra_urls(self) -> "Settings":
        """Accept platform-provided env vars (Render/Heroku style) and fix the
        Postgres scheme so SQLAlchemy uses the asyncpg driver.

        Precedence: explicit PITWALL_* wins; otherwise fall back to the
        conventional DATABASE_URL / REDIS_URL that Render injects.
        """
        if not self.database_url:
            self.database_url = os.environ.get("DATABASE_URL")
        if not self.redis_url:
            self.redis_url = os.environ.get("REDIS_URL")

        if self.database_url:
            u = self.database_url
            if u.startswith("postgres://"):
                u = "postgresql+asyncpg://" + u[len("postgres://"):]
            elif u.startswith("postgresql://") and "+asyncpg" not in u:
                u = "postgresql+asyncpg://" + u[len("postgresql://"):]
            # asyncpg rejects libpq-style ?sslmode=; drop it (internal conns
            # don't need it; for external use ?ssl=require instead).
            if "sslmode=" in u:
                u = u.split("?")[0]
            self.database_url = u
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
