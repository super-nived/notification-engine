"""Integration tests for the /api/v1/rules endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.engine import Base, get_db
from app.engine.registry import RULE_REGISTRY
from main import app

# ── In-memory SQLite for tests ────────────────────────────────
TEST_DB_URL = "sqlite:///./test_rules.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine)


def override_get_db():
    """Provide a test DB session instead of the production one."""
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    """Create and drop all tables around each test."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


client = TestClient(app, raise_server_exceptions=False)


def test_list_rules_empty():
    """GET /rules/ should return empty list when no rules exist."""
    response = client.get("/api/v1/rules/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"] == []


def test_create_rule_invalid_class():
    """POST /rules/ should reject unknown rule_class with 400."""
    payload = {
        "name": "test_rule",
        "rule_class": "NonExistentRule",
        "schedule": "* * * * *",
    }
    response = client.post("/api/v1/rules/", json=payload)
    assert response.status_code in (400, 422)


def test_get_rule_not_found():
    """GET /rules/999 should return 404 when rule does not exist."""
    response = client.get("/api/v1/rules/999")
    assert response.status_code == 404
