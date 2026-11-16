"""Scraping endpoints: list sources, start a run, inspect past runs."""

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import get_settings
from app.deps import ScrapeServiceDep
from app.schemas.scrape import ScrapeRequest, ScrapeRunSummary, SourceInfo
from app.scrapers.fetcher import FetchError
from app.scrapers.registry import UnknownSourceError
from app.services.scrape_service import RunNotFoundError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sources", response_model=list[SourceInfo], summary="List available scraping sources")
def list_sources(service: ScrapeServiceDep) -> list[SourceInfo]:
    """Return every registered source together with the fields it extracts."""
    return service.list_sources()


@router.post(
    "/scrape",
    response_model=ScrapeRunSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Run a scrape job and persist its output",
)
def run_scrape(payload: ScrapeRequest, service: ScrapeServiceDep) -> ScrapeRunSummary:
    """Scrape a source synchronously and return the run summary.

    Results are written to ``data/runs/<run_id>/items.jsonl``; the run itself is
    recorded in ``summary.json`` next to the data.
    """
    settings = get_settings()
    if payload.max_pages > settings.max_pages_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"max_pages must be <= {settings.max_pages_limit}",
        )

    try:
        return service.run(payload.source_key, payload.max_pages, use_cache=payload.use_cache)
    except UnknownSourceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FetchError as exc:
        logger.warning("Scrape failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/runs", response_model=list[ScrapeRunSummary], summary="List recent scrape runs")
def list_runs(
    service: ScrapeServiceDep,
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of runs to return"),
) -> list[ScrapeRunSummary]:
    """Return persisted run summaries, newest first."""
    return service.list_runs(limit=limit)


@router.get("/runs/{run_id}", response_model=ScrapeRunSummary, summary="Get one scrape run")
def get_run(run_id: str, service: ScrapeServiceDep) -> ScrapeRunSummary:
    """Return the summary of a single run."""
    try:
        return service.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found"
        ) from exc
