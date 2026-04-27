from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.cache.client import close_cache, init_cache
from app.config import settings
from app.core.datetime_utils import utcnow
from app.core.exceptions import setup_exception_handlers
from app.core.logger import logger
from app.db.session_runtime import close_db, init_db
from app.middleware.logging_middleware import LoggingMiddleware
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


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": utcnow().isoformat() + "Z",
    }
