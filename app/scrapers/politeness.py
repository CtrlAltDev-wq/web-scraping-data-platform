"""Politeness primitives shared by every fetch strategy.

The HTTP fetcher and the browser fetcher must behave like the same well-mannered
client: check ``robots.txt`` before the first request to a host and never fire two
requests at the same host back to back. Keeping those rules in one module guarantees
the two implementations cannot drift apart.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Cache and query ``robots.txt`` rules per origin.

    Parsers are cached in memory so a crawl checks each host once. ``robots.txt`` is
    downloaded with a plain HTTP client even when pages are rendered by a browser:
    it is a small text file and does not need JavaScript.
    """

    def __init__(self, client: httpx.Client, user_agent: str, *, enabled: bool = True) -> None:
        self._client = client
        self._user_agent = user_agent
        self._enabled = enabled
        self._parsers: dict[str, RobotFileParser | None] = {}

    def is_allowed(self, url: str) -> bool:
        """Return whether ``url`` may be fetched under the host's robots.txt rules."""
        if not self._enabled:
            return True

        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin not in self._parsers:
            self._parsers[origin] = self._load(origin)

        parser = self._parsers[origin]
        if parser is None:
            # A missing or unreachable robots.txt means no declared restrictions.
            return True

        allowed = parser.can_fetch(self._user_agent, url)
        if not allowed:
            logger.warning("robots.txt disallows %s", url)
        return allowed

    def _load(self, origin: str) -> RobotFileParser | None:
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


class HostThrottle:
    """Keep at least ``delay_seconds`` between two requests to the same host."""

    def __init__(self, delay_seconds: float) -> None:
        self._delay_seconds = delay_seconds
        self._last_request_at: dict[str, float] = {}

    def wait(self, url: str) -> None:
        """Block until the host is allowed to receive another request."""
        host = urlparse(url).netloc
        last_request = self._last_request_at.get(host)
        if last_request is not None:
            remaining = self._delay_seconds - (time.monotonic() - last_request)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at[host] = time.monotonic()
