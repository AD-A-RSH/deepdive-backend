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
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "DeepDive R&D — Backend API for content creator poll intelligence.\n\n"
            "All creator endpoints require a Bearer JWT obtained from POST /api/auth/login.\n"
            "Fan-vote endpoints (/api/vote/*) are public."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/health", tags=["Health"], include_in_schema=False)
    def health_check():
        return JSONResponse({"status": "ok", "version": settings.APP_VERSION})

    return app


app = create_app()