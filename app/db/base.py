"""
app/db/base.py
──────────────
Import every model here so Alembic's ``env.py`` can discover them via a
single ``from app.db.base import Base`` import.

Adding a new model?  Just add its import below — no other Alembic changes
needed.
"""

from app.db.base_class import Base          # noqa: F401 — re-exported
from app.models.user import User            # noqa: F401
from app.models.poll import Poll            # noqa: F401
from app.models.question import Question   # noqa: F401
from app.models.option import Option       # noqa: F401
from app.models.vote import Vote           # noqa: F401
from app.models.answer import Answer       # noqa: F401
