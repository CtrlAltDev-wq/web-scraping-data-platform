"""Tests for the scrape service: persistence, lookup and error handling."""

import json
from pathlib import Path

import pytest
from fakes import FakeFetcher

from app.core.config import Settings
from app.scrapers.registry import UnknownSourceError
from app.services.scrape_service import RunNotFoundError, ScrapeService

FIXTURE = Path(__file__).parent / "fixtures" / "books_page_1.html"


def make_service(tmp_path: Path, pages: dict[int, str] | None = None) -> ScrapeService:
    settings = Settings(data_dir=tmp_path, request_delay_seconds=0, _env_file=None)
    html = FIXTURE.read_text(encoding="utf-8")
    fetcher = FakeFetcher(settings, pages or {1: html})
    return ScrapeService(settings, fetcher=fetcher)


def test_list_sources_returns_registered_metadata(tmp_path: Path) -> None:
    sources = make_service(tmp_path).list_sources()

    assert len(sources) == 3
    assert sources[0].key == "books-toscrape"
    assert "price" in sources[0].fields


def test_run_persists_items_and_summary(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    summary = service.run("books-toscrape", max_pages=1)

    assert summary.item_count == 3
    assert summary.pages_fetched == 1
    assert summary.errors == []
    assert len(summary.sample_items) == 3

    items_path = service._settings.data_dir / summary.output_path  # noqa: SLF001
    lines = items_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0])["title"] == "A Light in the Attic"

    summary_path = items_path.parent / "summary.json"
    assert summary_path.exists()


def test_get_run_and_list_runs_read_persisted_files(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    summary = service.run("books-toscrape", max_pages=1)

    persisted = service.get_run(summary.run_id)

    assert persisted.run_id == summary.run_id
    assert persisted.item_count == 3
    assert [run.run_id for run in service.list_runs()] == [summary.run_id]


def test_unknown_source_key_is_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(UnknownSourceError):
        service.run("does-not-exist", max_pages=1)


def test_missing_run_id_raises_not_found(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(RunNotFoundError):
        service.get_run("20260101T000000-abcdef")

    with pytest.raises(RunNotFoundError):
        # Path traversal attempts must never reach the filesystem.
        service.get_run("../../etc/passwd")
