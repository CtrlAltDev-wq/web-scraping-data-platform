"""Base contract shared by every scraper."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from app.core.config import Settings
from app.scrapers.fetcher import Fetcher


@dataclass(slots=True)
class ScrapeOutcome:
    """What a scraper produced during one run."""

    items: list[dict[str, Any]] = field(default_factory=list)
    pages_fetched: int = 0
    errors: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)


class BaseScraper(ABC):
    """Interface every site scraper implements.

    Subclasses declare metadata (used by ``GET /api/v1/sources`` and the CLI) and
    implement :meth:`scrape`, which returns plain dictionaries so records can be
    written to JSONL, CSV or a database without a rigid schema.

    ``requires_browser`` tells the service which fetch strategy to inject: setting it
    to ``True`` is the only change needed to scrape a JavaScript-rendered site.
    """

    source_key: ClassVar[str]
    display_name: ClassVar[str]
    description: ClassVar[str]
    base_url: ClassVar[str]
    record_fields: ClassVar[tuple[str, ...]]
    requires_browser: ClassVar[bool] = False
    # Fields that identify a record across runs. Volatile values (price, stock,
    # timestamps) are intentionally excluded so a re-crawl updates nothing.
    fingerprint_fields: ClassVar[tuple[str, ...]] = ()

    def __init__(self, fetcher: Fetcher) -> None:
        self._fetcher = fetcher

    @property
    def settings(self) -> Settings:
        """Expose settings to subclasses without a second constructor argument."""
        return self._fetcher.settings

    @abstractmethod
    def scrape(self, max_pages: int, *, use_cache: bool = False) -> ScrapeOutcome:
        """Collect records from at most ``max_pages`` listing pages."""
        raise NotImplementedError
