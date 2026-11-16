"""Test doubles shared across test modules."""

import re
from pathlib import Path

from app.core.config import Settings
from app.scrapers.fetcher import FetchResult


class FakeFetcher:
    """Serve local HTML instead of performing network requests."""

    def __init__(self, settings: Settings, pages: dict[int, str]) -> None:
        self.settings = settings
        self.pages = pages
        self.requested_pages: list[int] = []
        self.cache_writes: list[Path] = []

    def get(
        self,
        url: str,
        *,
        cache_path: Path | None = None,
        use_cache: bool = False,
    ) -> FetchResult:
        page = int(re.search(r"page-(\d+)", url).group(1))
        self.requested_pages.append(page)
        if cache_path is not None:
            self.cache_writes.append(cache_path)
        # Unknown pages behave like an empty catalogue page, which ends pagination.
        html = self.pages.get(page, "<html><body></body></html>")
        return FetchResult(url=url, status_code=200, html=html)
