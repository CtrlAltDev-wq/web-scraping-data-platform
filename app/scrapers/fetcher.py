"""HTTP fetching with politeness rules: robots.txt, throttling, retries and caching."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import Settings

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
        # Cache one robots.txt parser per origin and the last request time per host.
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last_request_at: dict[str, float] = {}

    def get(
        self,
        url: str,
        *,
        cache_path: Path | None = None,
        use_cache: bool = False,
    ) -> FetchResult:
        """Download ``url`` as text, optionally reusing a previously saved copy."""
        if use_cache and cache_path is not None and cache_path.exists():
            logger.info("Cache hit: %s", cache_path)
            return FetchResult(
                url=url,
                status_code=200,
                html=cache_path.read_text(encoding="utf-8"),
                from_cache=True,
            )

        if self.settings.respect_robots_txt and not self._is_allowed(url):
            raise FetchError(f"Blocked by robots.txt: {url}")

        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            self._throttle(url)
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

    def _throttle(self, url: str) -> None:
        """Sleep so two requests to the same host are never fired back to back."""
        host = urlparse(url).netloc
        last_request = self._last_request_at.get(host)
        if last_request is not None:
            elapsed = time.monotonic() - last_request
            remaining = self.settings.request_delay_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at[host] = time.monotonic()

    def _is_allowed(self, url: str) -> bool:
        """Check ``url`` against the host's robots.txt rules."""
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)

        parser = self._robots[origin]
        if parser is None:
            # A missing or unreachable robots.txt means no declared restrictions.
            return True
        allowed = parser.can_fetch(self.settings.user_agent, url)
        if not allowed:
            logger.warning("robots.txt disallows %s", url)
        return allowed

    def _load_robots(self, origin: str) -> RobotFileParser | None:
        robots_url = f"{origin}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            response = self._client.get(robots_url)
        except httpx.HTTPError as exc:
            logger.warning("robots.txt unavailable for %s: %s", origin, exc)
            return None

        if response.status_code != 200:
            logger.info(
                "robots.txt returned %s for %s; treating as unrestricted",
                response.status_code,
                origin,
            )
            return None

        parser.parse(response.text.splitlines())
        return parser
