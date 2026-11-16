"""Scraper for https://books.toscrape.com, a public sandbox bookstore.

The site is published by Zyte specifically for scraping practice, which makes it a
safe, always-available demo source for this platform. The parser is intentionally
separated from the HTTP layer so it can be unit-tested against a saved HTML fixture.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScrapeOutcome
from app.scrapers.fetcher import FetchError

# The star rating is encoded as a CSS class such as "star-rating Three".
RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
CURRENCY_BY_SYMBOL = {"£": "GBP", "$": "USD", "€": "EUR"}
PRICE_PATTERN = re.compile(r"([£$€])\s*([\d.,]+)")


class BooksToscrapeScraper(BaseScraper):
    """Collect book title, price, stock status and rating from the catalogue."""

    source_key = "books-toscrape"
    display_name = "Books to Scrape (demo catalogue)"
    description = (
        "Public sandbox bookstore maintained for scraping practice. "
        "Use it to try the platform without touching a client's website."
    )
    base_url = "https://books.toscrape.com"
    record_fields = (
        "title",
        "price",
        "currency",
        "availability",
        "rating",
        "product_url",
        "image_url",
        "collected_at",
    )
    # Title plus product URL stays stable even when the price or stock changes.
    fingerprint_fields = ("title", "product_url")

    PAGE_URL_TEMPLATE = "https://books.toscrape.com/catalogue/page-{page}.html"

    def scrape(self, max_pages: int, *, use_cache: bool = False) -> ScrapeOutcome:
        outcome = ScrapeOutcome()

        for page in range(1, max_pages + 1):
            url = self.PAGE_URL_TEMPLATE.format(page=page)
            cache_path = self.settings.raw_dir / self.source_key / f"page-{page:03d}.html"
            try:
                result = self._fetcher.get(url, cache_path=cache_path, use_cache=use_cache)
            except FetchError as exc:
                # A later page failing should not discard the pages already parsed.
                outcome.errors.append(str(exc))
                break

            outcome.pages_fetched += 1
            page_items = self.parse_listing(result.html, page_url=url)
            if not page_items:
                # No products means we walked past the last catalogue page.
                break
            outcome.items.extend(page_items)

        return outcome

    @classmethod
    def parse_listing(cls, html: str, page_url: str) -> list[dict[str, Any]]:
        """Parse one catalogue page into records.

        Kept side-effect free and callable on the class so tests can feed a static
        HTML fixture without constructing an HTTP client.
        """
        soup = BeautifulSoup(html, "html.parser")
        collected_at = datetime.now(UTC).isoformat(timespec="seconds")
        records: list[dict[str, Any]] = []

        for card in soup.select("article.product_pod"):
            title_link = card.select_one("h3 a")
            price_node = card.select_one("p.price_color")
            stock_node = card.select_one("p.instock.availability")
            rating_node = card.select_one("p.star-rating")
            image_node = card.select_one("img")

            if title_link is None or price_node is None:
                # Skip malformed cards instead of failing the whole page.
                continue

            price_text = price_node.get_text(strip=True)
            price, currency = cls._parse_price(price_text)
            rating = cls._parse_rating(rating_node["class"] if rating_node else [])

            records.append(
                {
                    "title": title_link.get("title") or title_link.get_text(strip=True),
                    "price": price,
                    "currency": currency,
                    "availability": stock_node.get_text(" ", strip=True) if stock_node else "",
                    "rating": rating,
                    "product_url": urljoin(page_url, title_link.get("href", "")),
                    "image_url": urljoin(page_url, image_node.get("src", ""))
                    if image_node
                    else None,
                    "collected_at": collected_at,
                }
            )

        return records

    @staticmethod
    def _parse_price(text: str) -> tuple[float | None, str | None]:
        match = PRICE_PATTERN.search(text)
        if match is None:
            return None, None
        symbol, amount = match.groups()
        try:
            value = float(amount.replace(",", ""))
        except ValueError:
            return None, CURRENCY_BY_SYMBOL.get(symbol)
        return value, CURRENCY_BY_SYMBOL.get(symbol)

    @staticmethod
    def _parse_rating(classes: list[str] | str) -> int | None:
        if isinstance(classes, str):
            classes = classes.split()
        for name in classes:
            if name in RATING_WORDS:
                return RATING_WORDS[name]
        return None
