from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client with its own empty database, deleted after the test."""
    monkeypatch.setenv("MOMO_DB", str(tmp_path / "test.db"))
    with TestClient(app) as test_client:  # "with" runs the startup code that creates the tables
        yield test_client


@pytest.fixture
def user(client):
    """A client that is already logged in as alice."""
    log_in(client, "alice")
    return client


def log_in(client, username, password="password123"):
    client.post("/auth/register", json={"username": username, "password": password})
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def upload(client, filename):
    with open(DATA / filename, "rb") as f:
        return client.post("/upload", files={"file": (filename, f, "text/xml")})
