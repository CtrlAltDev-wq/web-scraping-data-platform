"""Persistence and query operations for scraped items.

The repository hides SQLAlchemy from the service and API layers: callers pass plain
dictionaries in and receive ORM rows out.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Engine, String, cast, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.config import Settings
from app.db.database import create_db_engine, create_session_factory
from app.db.models import Base, ScrapedItem
from app.services.fingerprint import build_fingerprint


class ItemRepository:
    """Store scraped records with de-duplication and answer queries about them."""

    def __init__(self, settings: Settings, engine: Engine | None = None) -> None:
        # Ensure the SQLite file's parent directory exists before the engine connects.
        settings.ensure_directories()
        self._engine = engine or create_db_engine(settings)
        self._session_factory = create_session_factory(self._engine)
        # Iteration 3 creates the schema at startup; Alembic migrations arrive later.
        Base.metadata.create_all(self._engine)

    def add_items(
        self,
        source_key: str,
        items: list[dict],
        *,
        fingerprint_fields: tuple[str, ...],
        run_id: str,
    ) -> tuple[int, int]:
        """Insert new records and skip ones already stored.

        Returns ``(inserted, duplicated)``. The unique index on
        ``(source_key, fingerprint)`` makes the insert idempotent, so running the same
        crawl twice never creates a second row.
        """
        if not items:
            return 0, 0

        seen_at = datetime.now(UTC)
        rows = [
            {
                "source_key": source_key,
                "fingerprint": build_fingerprint(item, fingerprint_fields),
                "run_id": run_id,
                "data": item,
                "first_seen_at": seen_at,
            }
            for item in items
        ]
        statement = (
            sqlite_insert(ScrapedItem)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["source_key", "fingerprint"])
        )

        with self._session_factory() as session:
            result = session.execute(statement)
            session.commit()
            inserted = max(result.rowcount or 0, 0)

        return inserted, len(rows) - inserted

    def list_items(
        self,
        *,
        source_key: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, list[ScrapedItem]]:
        """Return one page of records plus the total number of matches."""
        filters = []
        if source_key:
            filters.append(ScrapedItem.source_key == source_key)
        if search:
            # Source fields differ, so search the serialized JSON payload. SQLite's
            # lower() only folds ASCII, which is enough for this portfolio dataset.
            pattern = f"%{search.casefold()}%"
            filters.append(func.lower(cast(ScrapedItem.data, String)).like(pattern))

        with self._session_factory() as session:
            total = session.scalar(select(func.count()).select_from(ScrapedItem).where(*filters))
            rows = session.scalars(
                select(ScrapedItem)
                .where(*filters)
                .order_by(ScrapedItem.id)
                .limit(limit)
                .offset(offset)
            ).all()

        return int(total or 0), list(rows)

    def get_item(self, item_id: int) -> ScrapedItem | None:
        """Return one record by primary key, or ``None`` when it does not exist."""
        with self._session_factory() as session:
            return session.get(ScrapedItem, item_id)

    def source_counts(self) -> list[tuple[str, int]]:
        """Return ``(source_key, item_count)`` pairs, sorted by source key."""
        with self._session_factory() as session:
            rows = session.execute(
                select(ScrapedItem.source_key, func.count(ScrapedItem.id))
                .group_by(ScrapedItem.source_key)
                .order_by(ScrapedItem.source_key)
            ).all()
        return [(source_key, int(count)) for source_key, count in rows]
