"""FastAPI dependency providers.

Services are cached per process so the HTTP connection pool inside ``HttpFetcher``
is reused across requests. Tests can override these dependencies with
``app.dependency_overrides``.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import get_settings
from app.services.scrape_service import ScrapeService


@lru_cache
def get_scrape_service() -> ScrapeService:
    """Return the shared scrape service for the current process."""
    settings = get_settings()
    settings.ensure_directories()
    return ScrapeService(settings)


ScrapeServiceDep = Annotated[ScrapeService, Depends(get_scrape_service)]
