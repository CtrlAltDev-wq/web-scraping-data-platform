"""API version 1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import scrape

api_router = APIRouter()
api_router.include_router(scrape.router, tags=["scraping"])
