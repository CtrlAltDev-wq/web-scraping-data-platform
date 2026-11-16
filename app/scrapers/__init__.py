"""Scraping package: fetchers, site scrapers and the source registry."""

from app.scrapers.base import BaseScraper, ScrapeOutcome
from app.scrapers.fetcher import FetchError, HttpFetcher

__all__ = ["BaseScraper", "FetchError", "HttpFetcher", "ScrapeOutcome"]
