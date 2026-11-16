"""Parser and paging tests for the quotes.toscrape.com sources."""

from pathlib import Path

from fakes import FakeFetcher

from app.core.config import Settings
from app.scrapers.quotes import QuotesJsScraper, QuotesStaticScraper, parse_quotes

FIXTURE = Path(__file__).parent / "fixtures" / "quotes_page_1.html"
PAGE_URL = "https://quotes.toscrape.com/page/1/"


def test_parse_quotes_extracts_core_fields() -> None:
    records = parse_quotes(FIXTURE.read_text(encoding="utf-8"), PAGE_URL)

    assert len(records) == 10
    first = records[0]
    assert first["quote"] == (
        "The world as we have created it is a process of our thinking. "
        "It cannot be changed without changing our thinking."
    )
    assert first["author"] == "Albert Einstein"
    assert first["tags"] == ["change", "deep-thoughts", "thinking", "world"]
    assert first["author_url"] == "https://quotes.toscrape.com/author/Albert-Einstein"
    assert first["source_url"] == PAGE_URL
    assert first["collected_at"].endswith("+00:00")


def test_parse_quotes_reads_authors_and_tags() -> None:
    records = parse_quotes(FIXTURE.read_text(encoding="utf-8"), PAGE_URL)

    assert records[1]["author"] == "J.K. Rowling"
    assert records[1]["tags"] == ["abilities", "choices"]
    assert all(isinstance(record["tags"], list) for record in records)


def test_static_scraper_pages_until_empty_page(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, request_delay_seconds=0, _env_file=None)
    html = FIXTURE.read_text(encoding="utf-8")
    fetcher = FakeFetcher(settings, pages={1: html, 2: html})
    scraper = QuotesStaticScraper(fetcher)

    outcome = scraper.scrape(max_pages=5)

    assert outcome.pages_fetched == 3
    assert len(outcome.items) == 20
    assert outcome.errors == []
    assert outcome.screenshots == []
    assert fetcher.requested_pages == [1, 2, 3]
    # The HTTP variant never asks for browser-specific features.
    assert fetcher.screenshot_writes == []
    assert fetcher.wait_for_selectors == [None, None, None]


def test_browser_scraper_requests_render_and_screenshots(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, request_delay_seconds=0, _env_file=None)
    html = FIXTURE.read_text(encoding="utf-8")
    fetcher = FakeFetcher(settings, pages={1: html})
    scraper = QuotesJsScraper(fetcher)

    outcome = scraper.scrape(max_pages=1)

    assert len(outcome.items) == 10
    assert outcome.screenshots == ["screenshots/quotes-js/page-001.png"]
    assert fetcher.wait_for_selectors == ["div.quote"]
    assert fetcher.screenshot_writes[0].name == "page-001.png"


def test_browser_scraper_stops_when_page_is_empty(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, request_delay_seconds=0, _env_file=None)
    html = FIXTURE.read_text(encoding="utf-8")
    fetcher = FakeFetcher(settings, pages={1: html, 2: html, 3: "<html></html>"})
    scraper = QuotesJsScraper(fetcher)

    outcome = scraper.scrape(max_pages=5)

    assert outcome.pages_fetched == 3
    assert len(outcome.items) == 20
