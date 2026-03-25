"""
app/db/session.py
─────────────────
SQLAlchemy engine + session factory wired to MySQL via PyMySQL.

Design Pattern : Unit of Work — each request gets its own Session that is
                 committed or rolled back as a single atomic unit.
Principle       : Dependency Inversion — FastAPI endpoints depend on the
                 abstract `get_db` generator, not on a concrete session.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
import pymysql
pymysql.install_as_MySQLdb()

# ── Engine ────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,       # Recycles stale connections automatically
    pool_recycle=3600,        # Force-recycle connections older than 1 h
    pool_size=10,             # Connections kept open in the pool
    max_overflow=20,          # Extra connections allowed under load
    echo=settings.DEBUG,      # Log SQL statements in dev mode
)

# ── Session factory ───────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # Prevent lazy-loading after commit
)


# ── FastAPI dependency ────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for the duration of a single HTTP request.

    Usage in endpoints::

        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...

    The session is always closed in the ``finally`` block regardless of
    whether the request succeeded or raised an exception.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
