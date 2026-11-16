"""API tests: health, source listing, scrape runs and stored-record queries."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes import FakeFetcher
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.deps import get_scrape_service
from app.main import app
from app.schemas.scrape import ScrapeRunSummary
from app.scrapers.registry import UnknownSourceError
from app.services.scrape_service import RunNotFoundError, ScrapeService

FIXTURE = Path(__file__).parent / "fixtures" / "books_page_1.html"


class StubScrapeService:
    """Service double used to test HTTP wiring without touching the network."""

    def list_sources(self) -> list:
        return []

    def run(self, source_key: str, max_pages: int, *, use_cache: bool = False) -> ScrapeRunSummary:
        if source_key != "books-toscrape":
            raise UnknownSourceError(source_key)
        now = datetime.now(UTC)
        return ScrapeRunSummary(
            run_id="20260101T000000-abcdef",
            source_key=source_key,
            source_name="Stub source",
            started_at=now,
            finished_at=now,
            duration_seconds=0.01,
            pages_fetched=max_pages,
            item_count=2,
            output_path="runs/20260101T000000-abcdef/items.jsonl",
            sample_items=[{"title": "Example"}],
        )

    def list_runs(self, limit: int = 20) -> list[ScrapeRunSummary]:
        return []

    def get_run(self, run_id: str) -> ScrapeRunSummary:
        raise RunNotFoundError(run_id)


@pytest.fixture
def stub_client(client: TestClient) -> Iterator[TestClient]:
    app.dependency_overrides[get_scrape_service] = lambda: StubScrapeService()
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_list_sources_exposes_registered_scraper(client: TestClient) -> None:
    response = client.get("/api/v1/sources")

    assert response.status_code == 200
    sources = response.json()
    assert sources[0]["key"] == "books-toscrape"
    assert "product_url" in sources[0]["fields"]


def test_scrape_endpoint_returns_run_summary(stub_client: TestClient) -> None:
    response = stub_client.post(
        "/api/v1/scrape",
        json={"source_key": "books-toscrape", "max_pages": 2},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["run_id"] == "20260101T000000-abcdef"
    assert body["item_count"] == 2


def test_scrape_endpoint_rejects_unknown_source(stub_client: TestClient) -> None:
    response = stub_client.post("/api/v1/scrape", json={"source_key": "unknown", "max_pages": 1})

    assert response.status_code == 404


def test_scrape_endpoint_enforces_page_limit(stub_client: TestClient) -> None:
    response = stub_client.post(
        "/api/v1/scrape",
        json={"source_key": "books-toscrape", "max_pages": 999},
    )

    assert response.status_code == 400


def test_missing_run_returns_404(stub_client: TestClient) -> None:
    response = stub_client.get("/api/v1/runs/20260101T000000-abcdef")

    assert response.status_code == 404


def test_items_endpoints_query_stored_records(tmp_path: Path, client: TestClient) -> None:
    settings = Settings(data_dir=tmp_path, request_delay_seconds=0, _env_file=None)
    fetcher = FakeFetcher(settings, pages={1: FIXTURE.read_text(encoding="utf-8")})
    service = ScrapeService(settings, fetcher=fetcher)
    service.run("books-toscrape", max_pages=1)

    app.dependency_overrides[get_scrape_service] = lambda: service
    try:
        page = client.get("/api/v1/items", params={"source_key": "books-toscrape", "limit": 2})
        assert page.status_code == 200
        body = page.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2

        item_id = body["items"][0]["id"]
        detail = client.get(f"/api/v1/items/{item_id}")
        assert detail.status_code == 200
        assert detail.json()["data"]["title"] == "A Light in the Attic"

        search = client.get("/api/v1/items", params={"q": "attic"})
        assert search.json()["total"] == 1

        stats = client.get("/api/v1/stats")
        assert stats.json() == [{"source_key": "books-toscrape", "item_count": 3}]

        assert client.get("/api/v1/items/999999").status_code == 404
    finally:
        app.dependency_overrides.clear()
