"""Command-line interface.

Examples:
    python -m app.cli sources
    python -m app.cli scrape --source books-toscrape --pages 2
"""

from __future__ import annotations

import argparse
import json
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.scrapers.fetcher import FetchError
from app.scrapers.registry import UnknownSourceError
from app.services.scrape_service import ScrapeService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Web scraping and data extraction platform CLI",
    )
    parser.add_argument("--log-level", default=None, help="Override the configured log level")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sources", help="List registered scraping sources")

    scrape_parser = subparsers.add_parser("scrape", help="Run a scraper and store its output")
    scrape_parser.add_argument("--source", required=True, help="Registered source key")
    scrape_parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help="Maximum number of listing pages (defaults to APP_DEFAULT_MAX_PAGES)",
    )
    scrape_parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Re-parse HTML saved in data/raw instead of downloading it again",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = get_settings()
    configure_logging(args.log_level or settings.log_level)
    settings.ensure_directories()
    service = ScrapeService(settings)

    if args.command == "sources":
        for source in service.list_sources():
            print(f"{source.key}: {source.name}")
            print(f"  url:     {source.base_url}")
            print(f"  fields:  {', '.join(source.fields)}")
            print(f"  browser: {'yes' if source.requires_browser else 'no'}")
        return 0

    max_pages = args.pages or settings.default_max_pages
    if max_pages > settings.max_pages_limit:
        print(f"error: --pages must be <= {settings.max_pages_limit}", file=sys.stderr)
        return 2

    try:
        summary = service.run(args.source, max_pages, use_cache=args.use_cache)
    except UnknownSourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
