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
        self.screenshot_writes: list[Path] = []
        self.wait_for_selectors: list[str | None] = []

    def get(
        self,
        url: str,
        *,
        cache_path: Path | None = None,
        use_cache: bool = False,
        screenshot_path: Path | None = None,
        wait_for_selector: str | None = None,
    ) -> FetchResult:
        page = int(re.search(r"page[-/](\d+)", url).group(1))
        self.requested_pages.append(page)
        if cache_path is not None:
            self.cache_writes.append(cache_path)
        if screenshot_path is not None:
            self.screenshot_writes.append(screenshot_path)
        self.wait_for_selectors.append(wait_for_selector)
        # Unknown pages behave like an empty listing page, which ends pagination.
        html = self.pages.get(page, "<html><body></body></html>")
        return FetchResult(
            url=url,
            status_code=200,
            html=html,
            screenshot_path=screenshot_path,
        )
