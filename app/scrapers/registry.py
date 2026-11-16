"""Registry of available scrapers.

Adding a site means writing a :class:`BaseScraper` subclass and appending its class to
``SCRAPER_CLASSES``; the API and the CLI pick it up automatically.
"""

from __future__ import annotations

from app.scrapers.base import BaseScraper
from app.scrapers.books_toscrape import BooksToscrapeScraper
from app.scrapers.quotes import QuotesJsScraper, QuotesStaticScraper

SCRAPER_CLASSES: dict[str, type[BaseScraper]] = {
    BooksToscrapeScraper.source_key: BooksToscrapeScraper,
    QuotesStaticScraper.source_key: QuotesStaticScraper,
    QuotesJsScraper.source_key: QuotesJsScraper,
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


def get_scraper_class(source_key: str) -> type[BaseScraper]:
    """Return the scraper class registered for ``source_key``.

    The service needs the class before it can choose a fetch strategy, because the
    class declares whether the source requires a browser.
    """
    try:
        return SCRAPER_CLASSES[source_key]
    except KeyError:
        raise UnknownSourceError(source_key) from None
