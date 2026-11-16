"""Browser-based fetch strategy for pages that render their content with JavaScript.

Plain HTTP returns the initial HTML document. When a site builds its listing in the
browser, that document is an empty shell, so this fetcher drives Chromium through
Playwright and returns the DOM after scripts have run.

A browser is launched per call. It is slower than reusing a single session, but it
keeps the fetcher stateless: nothing has to be closed by the API layer, and a crash
in one page cannot poison the next run.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from app.core.config import Settings
from app.scrapers.fetcher import FetchError, FetchResult
from app.scrapers.politeness import HostThrottle, RobotsChecker

logger = logging.getLogger(__name__)


class PlaywrightFetcher:
    """Render ``url`` in headless Chromium and return the resulting DOM."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        # robots.txt is a plain text file, so it is fetched without a browser.
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
        """Render ``url`` and return its HTML, optionally saving a screenshot.

        ``wait_for_selector`` lets a scraper wait for the element that proves the
        JavaScript rendering finished, instead of guessing with a fixed sleep.
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
                html, captured = self._render(
                    url,
                    screenshot_path=screenshot_path,
                    wait_for_selector=wait_for_selector,
                )
            except FetchError:
                # Missing Playwright or Chromium will not fix itself on a retry.
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= self.settings.max_retries:
                    break
                backoff = self.settings.retry_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Render failed (%s/%s) for %s: %s. Retrying in %.1fs",
                    attempt,
                    self.settings.max_retries,
                    url,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
                continue

            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(html, encoding="utf-8")
            logger.info("Rendered %s with Chromium (%s bytes)", url, len(html))
            return FetchResult(url=url, status_code=200, html=html, screenshot_path=captured)

        raise FetchError(
            f"Failed to render {url} after {self.settings.max_retries} attempts: {last_error}"
        )

    def _render(
        self,
        url: str,
        *,
        screenshot_path: Path | None,
        wait_for_selector: str | None,
    ) -> tuple[str, Path | None]:
        """Open one browser, load ``url`` and return ``(html, screenshot_path)``."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depends on the environment
            raise FetchError(
                "Playwright is not installed. Run: pip install -r requirements.txt"
            ) from exc

        captured: Path | None = None
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=self.settings.browser_headless)
            except Exception as exc:  # pragma: no cover - depends on the environment
                raise FetchError(
                    "Chromium is not available. Run: python -m playwright install chromium"
                ) from exc

            try:
                page = browser.new_page(user_agent=self.settings.user_agent)
                page.goto(
                    url,
                    wait_until="load",
                    timeout=self.settings.browser_timeout_ms,
                )
                if wait_for_selector is not None:
                    page.wait_for_selector(
                        wait_for_selector,
                        timeout=self.settings.browser_timeout_ms,
                    )
                html = page.content()
                if screenshot_path is not None:
                    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    captured = screenshot_path
            finally:
                browser.close()

        return html, captured
