"""Scrapers for https://quotes.toscrape.com, a public sandbox quote site.

The site is published for scraping practice and exposes the same markup in two
flavours:

- ``/page/N/`` serves every quote inside the initial HTML;
- ``/js/page/N/`` ships an empty container and fills it with JavaScript.

Shipping both makes the value of browser rendering measurable: the parser is shared,
only the fetch strategy changes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScrapeOutcome
from app.scrapers.fetcher import FetchError

# Quotes are wrapped in typographic quotation marks that are noise in a dataset.
QUOTE_MARKS = "\u201c\u201d\"'"


def parse_quotes(html: str, page_url: str) -> list[dict[str, Any]]:
    """Parse one quotes page into records.

    Side-effect free so tests can feed an HTML fixture directly. The same parser
    works for the server-rendered and the JavaScript-rendered page: Playwright
    returns the DOM after scripts run, which has identical markup.
    """
    soup = BeautifulSoup(html, "html.parser")
    collected_at = datetime.now(UTC).isoformat(timespec="seconds")
    records: list[dict[str, Any]] = []

    for block in soup.select("div.quote"):
        text_node = block.select_one("span.text")
        author_node = block.select_one("small.author")
        if text_node is None or author_node is None:
            # Skip malformed blocks instead of failing the whole page.
            continue

        about_link = block.select_one("span > a")
        records.append(
            {
                "quote": text_node.get_text(" ", strip=True).strip(QUOTE_MARKS).strip(),
                "author": author_node.get_text(strip=True),
                "tags": [tag.get_text(strip=True) for tag in block.select("div.tags a.tag")],
                "author_url": urljoin(page_url, about_link.get("href", "")) if about_link else None,
                "source_url": page_url,
                "collected_at": collected_at,
            }
        )

    return records


class _QuotesScraper(BaseScraper):
    """Paging loop shared by the HTTP and the browser variant."""

    page_url_template: ClassVar[str]
    wait_for_selector: ClassVar[str | None] = None

    def scrape(self, max_pages: int, *, use_cache: bool = False) -> ScrapeOutcome:
        outcome = ScrapeOutcome()

        for page in range(1, max_pages + 1):
            url = self.page_url_template.format(page=page)
            cache_path = self.settings.raw_dir / self.source_key / f"page-{page:03d}.html"
            screenshot_path = (
                self.settings.screenshots_dir / self.source_key / f"page-{page:03d}.png"
                if self.requires_browser
                else None
            )

            try:
                result = self._fetcher.get(
                    url,
                    cache_path=cache_path,
                    use_cache=use_cache,
                    screenshot_path=screenshot_path,
                    wait_for_selector=self.wait_for_selector,
                )
            except FetchError as exc:
                # A later page failing should not discard the pages already parsed.
                outcome.errors.append(str(exc))
                break

            outcome.pages_fetched += 1
            if result.screenshot_path is not None:
                outcome.screenshots.append(
                    result.screenshot_path.relative_to(self.settings.data_dir).as_posix()
                )

            page_items = parse_quotes(result.html, page_url=url)
            if not page_items:
                # No quotes means we walked past the last page.
                break
            outcome.items.extend(page_items)

        return outcome


class QuotesStaticScraper(_QuotesScraper):
    """Collect quotes from the server-rendered listing with plain HTTP."""

    source_key = "quotes-static"
    display_name = "Quotes to Scrape (server-rendered)"
    description = (
        "Public sandbox quote site whose quotes are present in the initial HTML. "
        "Baseline for comparing HTTP fetching with browser rendering."
    )
    base_url = "https://quotes.toscrape.com"
    record_fields = ("quote", "author", "tags", "author_url", "source_url", "collected_at")
    page_url_template = "https://quotes.toscrape.com/page/{page}/"


class QuotesJsScraper(_QuotesScraper):
    """Collect quotes from the JavaScript-rendered listing with Chromium."""

    source_key = "quotes-js"
    display_name = "Quotes to Scrape (JavaScript-rendered)"
    description = (
        "Same quote site, but the listing is built by JavaScript. Requires Playwright; "
        "each page is rendered in Chromium and saved as a screenshot as evidence."
    )
    base_url = "https://quotes.toscrape.com"
    record_fields = ("quote", "author", "tags", "author_url", "source_url", "collected_at")
    page_url_template = "https://quotes.toscrape.com/js/page/{page}/"
    requires_browser = True
    # Rendering is finished once the first quote exists in the DOM.
    wait_for_selector = "div.quote"
