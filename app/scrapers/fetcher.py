"""Fetch strategies: download page HTML, either over HTTP or with a real browser.

A scraper depends on the :class:`Fetcher` protocol only, so switching a source from
plain HTTP to browser rendering never touches parsing code.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import Settings
from app.scrapers.politeness import HostThrottle, RobotsChecker

logger = logging.getLogger(__name__)


class FetchError(RuntimeError):
    """Raised when a page cannot be downloaded after all retries."""


@dataclass(slots=True)
class FetchResult:
    """A downloaded (or cached) HTML document."""

    url: str
    status_code: int
    html: str
    from_cache: bool = False
    screenshot_path: Path | None = None


class Fetcher(Protocol):
    """What a scraper needs from a fetch strategy.

    Both :class:`HttpFetcher` and
    :class:`app.scrapers.playwright_fetcher.PlaywrightFetcher` satisfy it. Browser
    specific arguments are accepted by every implementation so a scraper can call
    all strategies through the same interface.
    """

    settings: Settings

    def get(
        self,
        url: str,
        *,
        cache_path: Path | None = None,
        use_cache: bool = False,
        screenshot_path: Path | None = None,
        wait_for_selector: str | None = None,
    ) -> FetchResult:
        """Return the HTML for ``url``."""
        ...


class HttpFetcher:
    """Small, reusable HTTP client for scrapers.

    Responsibilities:
    - obey ``robots.txt`` before the first request to a host,
    - wait at least ``request_delay_seconds`` between two requests to the same host,
    - retry transient network errors with exponential backoff,
    - keep the original HTML on disk so a parser can be re-run without re-crawling.
    """

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._client = client or httpx.Client(
            headers={"User-Agent": settings.user_agent},
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
        )
        self._robots = RobotsChecker(
            self._client,
            settings.user_agent,
            enabled=settings.respect_robots_txt,
        )
        self._throttle = HostThrottle(settings.request_delay_seconds)

    def get(
        self,
        url: str,
        *,
        cache_path: Path | None = None,
        use_cache: bool = False,
        screenshot_path: Path | None = None,
        wait_for_selector: str | None = None,
    ) -> FetchResult:
        """Download ``url`` as text, optionally reusing a previously saved copy.

        ``screenshot_path`` and ``wait_for_selector`` exist only for interface
        compatibility with the browser fetcher and are ignored here.
        """
        if use_cache and cache_path is not None and cache_path.exists():
            logger.info("Cache hit: %s", cache_path)
            return FetchResult(
                url=url,
                status_code=200,
                html=cache_path.read_text(encoding="utf-8"),
                from_cache=True,
            )

        if not self._robots.is_allowed(url):
            raise FetchError(f"Blocked by robots.txt: {url}")

        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            self._throttle.wait(url)
            try:
                response = self._client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= self.settings.max_retries:
                    break
                backoff = self.settings.retry_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Request failed (%s/%s) for %s: %s. Retrying in %.1fs",
                    attempt,
                    self.settings.max_retries,
                    url,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
                continue

            html = response.text
            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(html, encoding="utf-8")
            logger.info("Fetched %s (%s bytes)", url, len(html))
            return FetchResult(url=url, status_code=response.status_code, html=html)

        raise FetchError(
            f"Failed to fetch {url} after {self.settings.max_retries} attempts: {last_error}"
        )
