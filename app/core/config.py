"""
app/core/config.py
──────────────────
Centralised application configuration loaded from environment variables.

Design Pattern : Singleton (Settings loaded once, shared everywhere)
Principle       : Single Responsibility — one place owns all env vars
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings resolved from environment variables or a .env file.

    All attributes mirror the keys in .env.example.  Pydantic validates types
    automatically, so DATABASE_URL must be a valid DSN string, etc.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # ── Application ──────────────────────────────────
    APP_NAME: str = "DeepDive R&D API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # ── Database ─────────────────────────────────────
    DATABASE_URL: str = ""

    # ── JWT ──────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # ── CORS ─────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ── Frontend URL (used for building share links) ──
    # Set this in Railway to your Vercel URL.
    # NEVER leave this as "*" — it will corrupt poll share_url values.
    FRONTEND_URL: str = "http://localhost:5173"

    # ── First superuser ───────────────────────────────
    FIRST_SUPERUSER_EMAIL: str = "admin@deepdive.com"
    FIRST_SUPERUSER_PASSWORD: str = "changeme123"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse comma-separated origins string into a list."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings singleton.

    Using lru_cache ensures the .env file is read exactly once per process,
    matching the Singleton design pattern without an explicit class.
    """
    return Settings()


settings: Settings = get_settings()