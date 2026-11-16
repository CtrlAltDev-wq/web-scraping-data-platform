"""Health endpoint used by uptime checks and Docker health probes."""

import platform
import sys
from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    python_version: str
    time_utc: datetime


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return a lightweight liveness signal."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        python_version=platform.python_version() + f" ({sys.implementation.name})",
        time_utc=datetime.now(UTC),
    )
