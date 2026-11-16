"""Shared pytest fixtures."""

import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

# Point the default settings at a throwaway directory before ``app`` is imported, so
# API tests never write a database or run output into the real ``data`` folder.
os.environ.setdefault("APP_DATA_DIR", tempfile.mkdtemp(prefix="webscraping-tests-"))

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    """FastAPI test client with the application lifespan executed."""
    with TestClient(app) as test_client:
        yield test_client
