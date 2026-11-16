"""Pydantic models for the scraping API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    """Metadata describing one available scraping source."""

    key: str
    name: str
    description: str
    base_url: str
    fields: list[str]
    requires_browser: bool = Field(
        default=False,
        description="True when pages must be rendered in Chromium instead of fetched over HTTP",
    )


class ScrapeRequest(BaseModel):
    """Payload for starting a scrape run."""

    source_key: str = Field(default="books-toscrape", description="Registered source key")
    max_pages: int = Field(default=3, ge=1, description="Upper bound on listing pages to crawl")
    use_cache: bool = Field(
        default=False,
        description="Reuse previously downloaded HTML from data/raw instead of hitting the site",
    )


class ScrapeRunSummary(BaseModel):
    """Result of one scrape run, also persisted as ``summary.json``."""

    run_id: str
    source_key: str
    source_name: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    pages_fetched: int
    item_count: int
    items_inserted: int = Field(
        default=0,
        description="Records written to the database for the first time in this run",
    )
    items_duplicated: int = Field(
        default=0,
        description="Records already stored for this source and therefore skipped",
    )
    output_path: str
    errors: list[str] = Field(default_factory=list)
    screenshots: list[str] = Field(
        default_factory=list,
        description="Screenshot files captured by browser-based sources, relative to data/",
    )
    sample_items: list[dict[str, Any]] = Field(default_factory=list)
