"""Registry of available scrapers.

Adding a site means writing a :class:`BaseScraper` subclass and appending its class to
``SCRAPER_CLASSES``; the API and the CLI pick it up automatically.
"""

from __future__ import annotations

from app.scrapers.base import BaseScraper
from app.scrapers.books_toscrape import BooksToscrapeScraper
from app.scrapers.fetcher import HttpFetcher

SCRAPER_CLASSES: dict[str, type[BaseScraper]] = {
    BooksToscrapeScraper.source_key: BooksToscrapeScraper,
}


class UnknownSourceError(ValueError):
    """Raised when a caller asks for a source that is not registered."""

    def __init__(self, source_key: str) -> None:
        available = ", ".join(sorted(SCRAPER_CLASSES)) or "none"
        super().__init__(f"Unknown source '{source_key}'. Available sources: {available}")
        self.source_key = source_key


def available_sources() -> list[type[BaseScraper]]:
    """Return every registered scraper class."""
    return list(SCRAPER_CLASSES.values())


def build_scraper(source_key: str, fetcher: HttpFetcher) -> BaseScraper:
    """Instantiate the scraper registered for ``source_key``."""
    scraper_class = SCRAPER_CLASSES.get(source_key)
    if scraper_class is None:
        raise UnknownSourceError(source_key)
    return scraper_class(fetcher)
