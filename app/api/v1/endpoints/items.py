"""Query endpoints for stored, de-duplicated records."""

from fastapi import APIRouter, HTTPException, Query, status

from app.deps import ScrapeServiceDep
from app.schemas.items import ItemPage, ScrapedItemOut, SourceStats

router = APIRouter()


@router.get(
    "/items",
    response_model=ItemPage,
    summary="Query stored records",
)
def list_items(
    service: ScrapeServiceDep,
    source_key: str | None = Query(default=None, description="Filter by source key"),
    q: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
        description="Case-insensitive text search inside the record payload",
    ),
    limit: int = Query(default=20, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Records to skip"),
) -> ItemPage:
    """Return one page of records already stored in the database."""
    return service.list_items(source_key=source_key, search=q, limit=limit, offset=offset)


@router.get("/items/{item_id}", response_model=ScrapedItemOut, summary="Get one stored record")
def get_item(item_id: int, service: ScrapeServiceDep) -> ScrapedItemOut:
    """Return a single record by its database id."""
    item = service.get_item(item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found",
        )
    return item


@router.get("/stats", response_model=list[SourceStats], summary="Stored record counts per source")
def get_stats(service: ScrapeServiceDep) -> list[SourceStats]:
    """Show how many de-duplicated records each source currently has."""
    return service.stats()
