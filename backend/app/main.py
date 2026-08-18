"""FastAPI application factory + lifespan wiring."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import router as api_router
from app.cache.cache import cache
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.database import db
from app.db.repository import upsert_sessions
from app.news.routes import router as news_router
from app.season.routes import router as season_router
from app.season.service import season_service
from app.sources.factory import get_source

log = get_logger("main")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("Starting %s v%s (source=%s)", settings.app_name, __version__, settings.data_source)
    source = get_source()
    await source.startup()
    await cache.startup()
    await db.startup()
    await season_service.startup()
    # Warm the session catalog into Postgres if available (best-effort).
    try:
        rows = await source.get_sessions()
        await upsert_sessions([{
            "session_key": r.get("session_key"),
            "meeting_key": r.get("meeting_key"),
            "year": r.get("year"),
            "country": r.get("country_name") or r.get("country"),
            "circuit": r.get("circuit_short_name") or r.get("location"),
            "session_name": r.get("session_name"),
            **r,
        } for r in rows])
    except Exception as exc:  # noqa: BLE001
        log.warning("catalog warm-up skipped (%s)", exc)
    try:
        yield
    finally:
        await source.shutdown()
        await cache.shutdown()
        await db.shutdown()
        await season_service.shutdown()
        log.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Pit Wall API",
        version=__version__,
        description="Second-screen F1 data companion — timing, track map, telemetry, tyres.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    @app.middleware("http")
    async def cache_headers(request, call_next):
        """Запретить кэширование данных тайминга.

        Без этого браузер отдаёт из кэша ответы с постоянным URL (`/drivers`,
        `/track`, `/tyres`, `/bounds`), тогда как `/frame?offset=…` каждый раз
        новый — и экран показывает смесь старых и свежих данных. Для тайминга
        устаревшие данные хуже отсутствующих, поэтому no-store.
        """
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, must-revalidate"
        elif path == "/" or path.startswith("/assets/"):
            # Статика может кэшироваться, но обязана сверяться с сервером,
            # иначе после деплоя у пользователя остаётся старый интерфейс.
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.include_router(api_router)
    app.include_router(season_router)
    app.include_router(news_router)

    if settings.serve_frontend and FRONTEND_DIR.exists():
        # Serve the static SPA. index at "/", assets under their paths.
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        async def index() -> FileResponse:
            return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
