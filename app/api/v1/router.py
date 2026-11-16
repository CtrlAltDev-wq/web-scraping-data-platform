"""API version 1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import items, scrape

api_router = APIRouter()
api_router.include_router(scrape.router, tags=["scraping"])
api_router.include_router(items.router, tags=["items"])
