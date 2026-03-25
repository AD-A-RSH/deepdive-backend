"""
app/main.py
───────────
FastAPI application factory.

Design Pattern : Factory Method — create_app() builds and configures the
                 FastAPI instance, keeping startup logic testable and
                 isolated from the module-level import side-effects.
Principle       : Single Responsibility — this file only wires together
                 middleware, routers, and lifecycle hooks.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    On startup: initialise the database tables and seed the first superuser
    if they do not already exist.  This is idempotent — safe to run on
    every deploy.
    """
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield
    # Shutdown: add cleanup logic here if needed (e.g. close connection pools)


def create_app() -> FastAPI:
    """
    Build and configure the FastAPI application instance.

    Returns:
        A fully configured FastAPI app ready to be served by Uvicorn.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "DeepDive R&D — Backend API for content creator poll intelligence.\n\n"
            "All creator endpoints require a Bearer JWT obtained from POST /api/auth/login.\n"
            "Fan-vote endpoints (/api/vote/*) are public."
        ),
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────
    app.include_router(api_router)

    # ── Health check ──────────────────────────────────────────
    @app.get("/health", tags=["Health"], include_in_schema=False)
    def health_check():
        """Simple liveness probe for load balancers and CI."""
        return JSONResponse({"status": "ok", "version": settings.APP_VERSION})

    return app


# ── WSGI/ASGI entry point ─────────────────────────────────────
app = create_app()
