"""
app/db/init_db.py
─────────────────
Database initialisation and optional seeding of the first superuser.

Run once after creating the database:
    python -m app.db.init_db

This is intentionally separate from Alembic migrations — use Alembic for
schema changes in production; use this script only for bootstrapping.
"""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.db.base import Base  # noqa: F401 — registers all models with metadata
from app.models.user import User


def init_db(db: Session) -> None:
    """
    Create all tables and insert a default superuser if none exists.

    Args:
        db: Active database session.
    """
    # Create tables (safe to run multiple times — uses CREATE TABLE IF NOT EXISTS)
    Base.metadata.create_all(bind=engine)

    # Seed first superuser
    existing = db.query(User).filter(User.email == settings.FIRST_SUPERUSER_EMAIL).first()
    if not existing:
        user = User(
            email=settings.FIRST_SUPERUSER_EMAIL,
            hashed_password=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
            name="Admin Creator",
            avatar_initials="AC",
            plan="pro",
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"[init_db] Created superuser: {settings.FIRST_SUPERUSER_EMAIL}")
    else:
        print("[init_db] Superuser already exists — skipping seed.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        init_db(db)
        print("[init_db] Database initialised successfully.")
    finally:
        db.close()
