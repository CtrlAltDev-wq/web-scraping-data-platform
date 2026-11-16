"""Pydantic models for stored-record queries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScrapedItemOut(BaseModel):
    """A stored record with its bookkeeping metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_key: str
    run_id: str
    first_seen_at: datetime
    data: dict[str, Any]

    @field_validator("first_seen_at")
    @classmethod
    def assume_utc(cls, value: datetime) -> datetime:
        """SQLite stores no timezone; document that the value is UTC."""
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class ItemPage(BaseModel):
    """One page of query results."""

    total: int = Field(description="Number of records matching the filters")
    limit: int
    offset: int
    items: list[ScrapedItemOut]


class SourceStats(BaseModel):
    """How many records are stored for one source."""

    source_key: str
    item_count: int
