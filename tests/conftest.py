"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """FastAPI test client with the application lifespan executed."""
    with TestClient(app) as test_client:
        yield test_client
