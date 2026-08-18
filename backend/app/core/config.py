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


def _data_fingerprint() -> str:
    """Отпечаток набора данных — запасной вариант, если платформа не отдаёт
    хэш коммита. Меняется при пересборке (файлы перезаписываются), но не при
    простом перезапуске контейнера, поэтому кэш не сбрасывается зря.

    Читается только метаинформация файлов, содержимое не разбирается.
    """
    import hashlib
    from pathlib import Path

    from app import __version__

    h = hashlib.sha1(__version__.encode())
    fixtures = Path(__file__).resolve().parent.parent / "sources" / "fixtures"
    try:
        for p in sorted(fixtures.glob("*.json")):
            st = p.stat()
            h.update(f"{p.name}:{st.st_size}:{int(st.st_mtime)}".encode())
    except OSError:
        pass
    return h.hexdigest()[:12]


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

    # --- Season (Jolpica-F1, преемник Ergast) — ТЗ §2.2 -------------------
    jolpica_base_url: str = "https://api.jolpi.ca/ergast/f1/"
    jolpica_timeout_s: float = 20.0
    # Зачёты меняются раз в гоночный уик-энд — кэшируем надолго.
    season_ttl_s: int = 1800

    # --- News (ТЗ §10) ----------------------------------------------------
    news_timeout_s: float = 20.0
    news_ttl_s: int = 600          # SC-01: опрос раз в 5–15 мин
    news_limit: int = 60

    # --- Cache (Redis, optional) ------------------------------------------
    # When unreachable the app transparently falls back to an in-process LRU.
    redis_url: str | None = Field(default=None)
    cache_ttl_s: int = 30          # live-ish data
    cache_ttl_static_s: int = 3600  # immutable replay data / geometry
    # Окна тайминга кэшируются по «бакету» времени: ключ содержит сам интервал,
    # поэтому данные в нём неизменны и TTL может быть щедрым (устаревание
    # ограничено размером бакета, а не TTL).
    frame_bucket_s: float = 1.0
    cache_ttl_window_s: int = 300
    # Версия пространства имён кэша. Redis переживает передеплой, поэтому без
    # версионирования новый код читал бы данные, закэшированные старым (список
    # пилотов, геометрия трассы, стинты) — на экране получалась бы смесь старых
    # и новых данных. Значение подставляется из хэша коммита при деплое.
    cache_version: str | None = Field(default=None)

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

    @property
    def poll_interval_ms(self) -> int:
        """Как часто фронтенду опрашивать бэкенд.

        Фикстур лежит локально — можно часто. Живой OpenF1 имеет лимиты
        бесплатного тарифа (DR-05), поэтому опрос реже, а плавность движения
        машин на карте обеспечивается интерполяцией на клиенте.
        """
        return 1500 if self.data_source == "openf1" else 300

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

        if not self.cache_version:
            # Render (и большинство PaaS) отдаёт хэш коммита в окружении —
            # он меняется при каждом деплое, что и нужно.
            commit = (
                os.environ.get("RENDER_GIT_COMMIT")
                or os.environ.get("SOURCE_VERSION")       # Heroku
                or os.environ.get("GIT_COMMIT")
            )
            self.cache_version = commit[:12] if commit else _data_fingerprint()

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
