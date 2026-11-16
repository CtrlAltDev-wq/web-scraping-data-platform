"""ORM models for the scraped records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for every table in the project."""


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp used as a column default."""
    return datetime.now(UTC)


class ScrapedItem(Base):
    """One de-duplicated record collected from a source.

    Records keep their original shape inside a JSON column: the fields differ per
    source, and a fixed table per site would multiply migrations. The fingerprint is
    the part the database must enforce, so repeated runs stay idempotent.
    """

    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("source_key", "fingerprint", name="uq_items_source_fingerprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
