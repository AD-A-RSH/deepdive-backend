"""
app/db/base_class.py
────────────────────
Declarative base shared by every SQLAlchemy model.

Keeping the Base in its own module avoids circular imports when Alembic
imports all models to generate migration scripts.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Common base class for all ORM models.

    Subclasses automatically get:
    - A ``__tablename__`` that mirrors the class name in snake_case
      (unless explicitly overridden).
    - The SQLAlchemy metadata registry used by Alembic.
    """
    pass
