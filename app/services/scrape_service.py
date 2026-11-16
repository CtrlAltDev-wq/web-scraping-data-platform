"""Scrape orchestration: run a scraper, archive the output and store clean records."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import Settings
from app.db.repository import ItemRepository
from app.schemas.items import ItemPage, ScrapedItemOut, SourceStats
from app.schemas.scrape import ScrapeRunSummary, SourceInfo
from app.scrapers.base import BaseScraper
from app.scrapers.fetcher import Fetcher, HttpFetcher
from app.scrapers.playwright_fetcher import PlaywrightFetcher
from app.scrapers.registry import (
    UnknownSourceError,
    available_sources,
    get_scraper_class,
)

logger = logging.getLogger(__name__)

# Run ids are used as directory names, so only allow a safe character set.
RUN_ID_PATTERN = re.compile(r"^[0-9A-Za-z\-]+$")


class RunNotFoundError(LookupError):
    """Raised when a run id has no persisted summary."""


class ScrapeService:
    """Coordinates fetchers, scrapers, the run store and the item database."""

    def __init__(
        self,
        settings: Settings,
        fetcher: Fetcher | None = None,
        repository: ItemRepository | None = None,
    ) -> None:
        self._settings = settings
        self._fetcher = fetcher or HttpFetcher(settings)
        # An injected fetcher (tests, custom wiring) always wins, even for sources
        # that would normally ask for a browser.
        self._fetcher_injected = fetcher is not None
        self._repository = repository or ItemRepository(settings)

    def _fetcher_for(self, scraper_class: type[BaseScraper]) -> Fetcher:
        """Return the fetch strategy the scraper needs.

        Browser sources get a fresh :class:`PlaywrightFetcher` so a long-lived API
        process never keeps a Chromium instance around between requests.
        """
        if scraper_class.requires_browser and not self._fetcher_injected:
            return PlaywrightFetcher(self._settings)
        return self._fetcher

    def list_sources(self) -> list[SourceInfo]:
        """Describe every registered source for the API and the CLI."""
        return [
            SourceInfo(
                key=scraper_class.source_key,
                name=scraper_class.display_name,
                description=scraper_class.description,
                base_url=scraper_class.base_url,
                fields=list(scraper_class.record_fields),
                requires_browser=scraper_class.requires_browser,
            )
            for scraper_class in available_sources()
        ]

    def run(self, source_key: str, max_pages: int, *, use_cache: bool = False) -> ScrapeRunSummary:
        """Scrape ``source_key`` and write ``items.jsonl`` plus ``summary.json``.

        Raises :class:`UnknownSourceError` for an unregistered source and
        :class:`app.scrapers.fetcher.FetchError` when the first page cannot be fetched.
        """
        self._settings.ensure_directories()
        scraper_class = get_scraper_class(source_key)
        scraper = scraper_class(self._fetcher_for(scraper_class))

        run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:6]}"
        started_at = datetime.now(UTC)
        logger.info("Starting run %s for %s (max_pages=%s)", run_id, source_key, max_pages)

        outcome = scraper.scrape(max_pages, use_cache=use_cache)

        finished_at = datetime.now(UTC)
        run_dir = self._settings.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        items_path = run_dir / "items.jsonl"
        items_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in outcome.items),
            encoding="utf-8",
        )

        inserted, duplicated = self._repository.add_items(
            scraper.source_key,
            outcome.items,
            fingerprint_fields=self._fingerprint_fields(scraper_class),
            run_id=run_id,
        )

        summary = ScrapeRunSummary(
            run_id=run_id,
            source_key=scraper.source_key,
            source_name=scraper.display_name,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round((finished_at - started_at).total_seconds(), 3),
            pages_fetched=outcome.pages_fetched,
            item_count=len(outcome.items),
            items_inserted=inserted,
            items_duplicated=duplicated,
            output_path=items_path.relative_to(self._settings.data_dir).as_posix(),
            errors=outcome.errors,
            screenshots=outcome.screenshots,
            sample_items=outcome.items[:3],
        )
        (run_dir / "summary.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        logger.info(
            "Run %s finished: %s items from %s pages (%s new, %s duplicates)",
            run_id,
            summary.item_count,
            summary.pages_fetched,
            inserted,
            duplicated,
        )
        return summary

    @staticmethod
    def _fingerprint_fields(scraper_class: type[BaseScraper]) -> tuple[str, ...]:
        """Identity fields for de-duplication.

        Sources declare them explicitly. The fallback ignores ``*_at`` collection
        timestamps so a default implementation never dedupes on crawl time.
        """
        return scraper_class.fingerprint_fields or tuple(
            name for name in scraper_class.record_fields if not name.endswith("_at")
        )

    def list_items(
        self,
        *,
        source_key: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ItemPage:
        """Return one page of stored records with the total match count."""
        total, rows = self._repository.list_items(
            source_key=source_key,
            search=search,
            limit=limit,
            offset=offset,
        )
        return ItemPage(
            total=total,
            limit=limit,
            offset=offset,
            items=[ScrapedItemOut.model_validate(row) for row in rows],
        )

    def get_item(self, item_id: int) -> ScrapedItemOut | None:
        """Return one stored record, or ``None`` when the id is unknown."""
        row = self._repository.get_item(item_id)
        return None if row is None else ScrapedItemOut.model_validate(row)

    def stats(self) -> list[SourceStats]:
        """Return the stored record count per source."""
        return [
            SourceStats(source_key=source_key, item_count=count)
            for source_key, count in self._repository.source_counts()
        ]

    def list_runs(self, limit: int = 20) -> list[ScrapeRunSummary]:
        """Return the most recent run summaries, newest first."""
        if not self._settings.runs_dir.exists():
            return []

        summaries: list[ScrapeRunSummary] = []
        for summary_path in sorted(self._settings.runs_dir.glob("*/summary.json"), reverse=True):
            try:
                summaries.append(
                    ScrapeRunSummary.model_validate_json(summary_path.read_text(encoding="utf-8"))
                )
            except (OSError, ValueError) as exc:
                logger.warning("Skipping unreadable run summary %s: %s", summary_path, exc)
            if len(summaries) >= limit:
                break
        return summaries

    def get_run(self, run_id: str) -> ScrapeRunSummary:
        """Load one persisted run summary by id."""
        if not RUN_ID_PATTERN.match(run_id):
            raise RunNotFoundError(run_id)
        summary_path = self._settings.runs_dir / run_id / "summary.json"
        if not summary_path.exists():
            raise RunNotFoundError(run_id)
        return ScrapeRunSummary.model_validate_json(summary_path.read_text(encoding="utf-8"))


__all__ = ["RunNotFoundError", "ScrapeService", "UnknownSourceError"]
