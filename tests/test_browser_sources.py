"""Service wiring for browser-based sources.

The tests replace ``PlaywrightFetcher`` with a fake, so no browser is launched and the
suite stays offline.
"""

from pathlib import Path

import pytest
from fakes import FakeFetcher

from app.core.config import Settings
from app.services.scrape_service import ScrapeService

FIXTURE = Path(__file__).parent / "fixtures" / "quotes_page_1.html"


def make_settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, request_delay_seconds=0, _env_file=None)


def test_browser_source_receives_playwright_fetcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    captured: dict[str, FakeFetcher] = {}

    def fake_playwright_fetcher(settings: Settings) -> FakeFetcher:
        captured["fetcher"] = FakeFetcher(settings, pages={1: html})
        return captured["fetcher"]

    monkeypatch.setattr(
        "app.services.scrape_service.PlaywrightFetcher",
        fake_playwright_fetcher,
    )

    settings = make_settings(tmp_path)
    summary = ScrapeService(settings).run("quotes-js", max_pages=1)

    assert "fetcher" in captured
    assert summary.item_count == 10
    assert summary.screenshots == ["screenshots/quotes-js/page-001.png"]
    assert (tmp_path / "runs" / summary.run_id / "items.jsonl").exists()


def test_non_browser_source_never_builds_a_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(settings: Settings) -> FakeFetcher:  # pragma: no cover - guard
        raise AssertionError("PlaywrightFetcher must not be used for HTTP sources")

    monkeypatch.setattr("app.services.scrape_service.PlaywrightFetcher", fail)

    settings = make_settings(tmp_path)
    fetcher = FakeFetcher(settings, pages={1: FIXTURE.read_text(encoding="utf-8")})
    summary = ScrapeService(settings, fetcher=fetcher).run("quotes-static", max_pages=1)

    assert summary.item_count == 10
    assert summary.screenshots == []


def test_sources_report_browser_requirement(tmp_path: Path) -> None:
    sources = {
        source.key: source for source in ScrapeService(make_settings(tmp_path)).list_sources()
    }

    assert set(sources) == {"books-toscrape", "quotes-static", "quotes-js"}
    assert sources["quotes-js"].requires_browser is True
    assert sources["quotes-static"].requires_browser is False
