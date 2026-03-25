"""
tests/test_auth.py
──────────────────
Unit + integration tests for authentication endpoints.

Uses an in-memory SQLite database so no MySQL is needed to run the test suite.

Run with:
    pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# ── In-memory SQLite for tests ────────────────────────────────
SQLALCHEMY_TEST_URL = "sqlite:///./test.db"

engine_test = create_engine(
    SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Tests ──────────────────────────────────────────────────────

def test_register_and_login(client):
    """A newly registered user can log in and receive a JWT."""
    from app.core.security import hash_password
    from app.models.user import User

    db = TestingSessionLocal()
    user = User(
        email="test@example.com",
        hashed_password=hash_password("secret123"),
        name="Test Creator",
        avatar_initials="TC",
    )
    db.add(user)
    db.commit()
    db.close()

    resp = client.post("/api/auth/login", json={"email": "test@example.com", "password": "secret123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client):
    """Wrong password returns 401."""
    resp = client.post("/api/auth/login", json={"email": "test@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_me_without_token(client):
    """GET /auth/me without a token returns 403 or 401."""
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


def test_health(client):
    """Health endpoint is always accessible."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
