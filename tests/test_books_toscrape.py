"""Parser and fetch-loop tests for the books.toscrape.com scraper."""

from pathlib import Path

from fakes import FakeFetcher

from app.core.config import Settings
from app.scrapers.books_toscrape import BooksToscrapeScraper

FIXTURE = Path(__file__).parent / "fixtures" / "books_page_1.html"
PAGE_URL = "https://books.toscrape.com/catalogue/page-1.html"


def test_parse_listing_extracts_core_fields() -> None:
    records = BooksToscrapeScraper.parse_listing(FIXTURE.read_text(encoding="utf-8"), PAGE_URL)

    assert len(records) == 3
    first = records[0]
    assert first["title"] == "A Light in the Attic"
    assert first["price"] == 51.77
    assert first["currency"] == "GBP"
    assert first["availability"] == "In stock"
    assert first["rating"] == 3
    assert first["product_url"] == (
        "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    )
    assert first["image_url"].startswith("https://books.toscrape.com/catalogue/media/")


def test_parse_listing_reads_rating_and_price_variants() -> None:
    records = BooksToscrapeScraper.parse_listing(FIXTURE.read_text(encoding="utf-8"), PAGE_URL)

    assert [record["rating"] for record in records] == [3, 1, 1]
    assert [record["price"] for record in records] == [51.77, 53.74, 50.1]


def test_scrape_follows_pagination_and_stops_on_empty_page(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, request_delay_seconds=0, _env_file=None)
    html = FIXTURE.read_text(encoding="utf-8")
    fetcher = FakeFetcher(settings, pages={1: html, 2: html})
    scraper = BooksToscrapeScraper(fetcher)

    outcome = scraper.scrape(max_pages=5)

    assert outcome.pages_fetched == 3
    assert len(outcome.items) == 6
    assert outcome.errors == []
    assert fetcher.requested_pages == [1, 2, 3]
