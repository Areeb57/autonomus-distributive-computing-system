"""
ADC Backend — FastAPI application entry point.

Creates the ASGI app, configures CORS, logging, exception handlers,
and mounts all API routers.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — runs on startup and shutdown."""
    settings = get_settings()

    # ── Startup ──────────────────────────────────────────────────────────
    setup_logging(
        log_level=settings.app_log_level,
        log_format="console" if settings.is_development else settings.log_format,
        log_file=settings.log_file if not settings.is_development else None,
        log_rotation_mb=settings.log_rotation_mb,
        log_retention_count=settings.log_retention_count,
    )

    logger = get_logger("adc.startup")
    logger.info(
        "starting_adc_backend",
        environment=settings.app_env,
        debug=settings.app_debug,
        database=settings.database_url.split("@")[-1] if "@" in settings.database_url else "configured",
    )

    # Ensure storage directories exist
    for directory in (
        settings.datasets_dir,
        settings.packages_dir,
        settings.checkpoints_dir,
        settings.logs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    # Test database connection and create tables if using SQLite
    from app.database.session import check_db_connection, engine

    if "sqlite" in settings.database_url:
        import app.models  # noqa: F401
        from app.database.base import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("sqlite_tables_created_or_verified")

    db_ok = await check_db_connection()
    if db_ok:
        logger.info("database_connected")
    else:
        logger.error("database_connection_failed_on_startup")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger = get_logger("adc.shutdown")
    logger.info("shutting_down_adc_backend")

    from app.database.session import engine
    await engine.dispose()
    logger.info("database_engine_disposed")


def create_app() -> FastAPI:
    """Factory function that builds and configures the FastAPI app."""
    settings = get_settings()

    app = FastAPI(
        title="ADC — Autonomous Distributed AI Trainer",
        description=(
            "Backend API for the ADC platform. Manages users, machines, "
            "projects, training jobs, and distributed compute coordination."
        ),
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # ── Middleware ───────────────────────────────────────────────────────
    from app.core.csrf import CSRFMiddleware

    app.add_middleware(CSRFMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ───────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ──────────────────────────────────────────────────────────
    from app.api.routes.health import router as health_router
    from app.api.routes.websocket import router as websocket_router
    from app.api.router import api_v1_router

    app.include_router(health_router)
    app.include_router(websocket_router)
    app.include_router(api_v1_router)

    return app


# The ASGI app instance used by uvicorn
app = create_app()
