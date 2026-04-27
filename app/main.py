from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.cache.client import cache_ping, close_cache, init_cache
from app.config import settings
from app.core.datetime_utils import utcnow
from app.core.exceptions import setup_exception_handlers
from app.core.logger import logger
from app.db.session_runtime import close_db, db_ping, init_db
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.request_guard import RequestGuardMiddleware
from app.tasks.queue import close_queue
from app.web.routes import web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск Manga Reader API...")
    logger.info(f"Environment: {'DEBUG' if settings.DEBUG else 'PRODUCTION'}")
    logger.info(f"Database: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")

    await init_db()
    await init_cache()
    yield
    await close_queue()
    await close_cache()
    await close_db()
    logger.info("Сервер остановлен")


app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

setup_exception_handlers(app)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

app.add_middleware(
    RequestGuardMiddleware,
    max_body_bytes=settings.MAX_REQUEST_BODY_BYTES,
    allowed_content_types=settings.ALLOWED_CONTENT_TYPES,
)
app.add_middleware(LoggingMiddleware)
app.include_router(api_router, prefix="/api/v1")
app.include_router(web_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    return {
        "message": "Manga Reader API with PostgreSQL and Redis",
        "docs": "/docs",
        "version": "2.1.0",
    }


def _component_status(value: bool | None) -> str:
    if value is None:
        return "disabled"
    return "ok" if value else "down"


@app.get("/health")
async def health_check():
    db_ok = await db_ping()
    cache_ok = await cache_ping()

    if db_ok:
        overall = "ok" if cache_ok is not False else "degraded"
    else:
        overall = "down"

    body = {
        "status": overall,
        "timestamp": utcnow().isoformat() + "Z",
        "components": {
            "database": _component_status(db_ok),
            "cache": _component_status(cache_ok),
        },
    }
    status_code = 200 if db_ok else 503
    return JSONResponse(body, status_code=status_code)


@app.get("/ready")
async def readiness_check():
    db_ok = await db_ping()
    cache_ok = await cache_ping()
    ready = bool(db_ok) and cache_ok is not False

    body = {
        "ready": ready,
        "timestamp": utcnow().isoformat() + "Z",
        "components": {
            "database": _component_status(db_ok),
            "cache": _component_status(cache_ok),
        },
    }
    return JSONResponse(body, status_code=200 if ready else 503)
