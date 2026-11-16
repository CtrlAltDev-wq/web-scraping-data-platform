# Web Scraping & Data Extraction Platform

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A Python platform that turns public web pages into clean, queryable data: crawl a site,
store the raw evidence, parse it into structured records, export reports and expose the
result through a documented REST API.

The repository is built in small, verifiable iterations. **Iteration 1 is complete**;
the roadmap below lists what comes next.

## What works today (iteration 1)

- FastAPI service with interactive OpenAPI docs at `/docs` and a `GET /health` probe
- A scraper registry so a new site is one class plus one registry line
- One real source: [`books.toscrape.com`](https://books.toscrape.com), a public sandbox
  bookstore published for scraping practice (20 books per listing page)
- HTTP fetcher with the politeness rules a real client expects:
  - `robots.txt` is checked before the first request to a host
  - requests to the same host are throttled (`APP_REQUEST_DELAY_SECONDS`)
  - transient failures are retried with exponential backoff
  - a descriptive `User-Agent` identifies the crawler
- Raw HTML is archived under `data/raw/<source>/page-001.html`, so a parser can be
  re-run without hitting the site again (`"use_cache": true`)
- BeautifulSoup parser extracting `title`, `price`, `currency`, `availability`,
  `rating`, `product_url`, `image_url` and `collected_at`
- Every run is persisted: `data/runs/<run_id>/items.jsonl` plus a `summary.json`
  with counters, duration and any page-level errors
- REST endpoints to list sources, start a run, list recent runs and read one run
- A small CLI (`python -m app.cli`) for the same operations without a server
- 14 pytest tests and Ruff lint/format checks

## Tech stack

| Layer | Technology |
| --- | --- |
| Web framework | FastAPI + Uvicorn |
| Validation / settings | Pydantic v2 + pydantic-settings |
| HTTP client | httpx |
| HTML parsing | BeautifulSoup 4 (`html.parser`) |
| Logging | Python `logging`, structured single-line output |
| Testing | pytest + FastAPI TestClient |
| Linting / formatting | Ruff |
| Storage (iteration 1) | JSONL + JSON on disk |
| Storage (planned) | SQLAlchemy 2.0 + SQLite, Alembic migrations |
| Browser automation (planned) | Playwright |
| Data processing (planned) | pandas + openpyxl |
| Scheduling (planned) | APScheduler |

## Quickstart

```bash
git clone https://github.com/CtrlAltDev-wq/web-scraping-data-platform.git
cd web-scraping-data-platform

python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
copy .env.example .env        # Windows; use `cp` on macOS/Linux
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs> and use **POST /api/v1/scrape** with:

```json
{ "source_key": "books-toscrape", "max_pages": 2 }
```

Or from the terminal:

```bash
# PowerShell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/scrape `
  -ContentType "application/json" `
  -Body '{"source_key": "books-toscrape", "max_pages": 2}'

# curl
curl -X POST http://127.0.0.1:8000/api/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{"source_key": "books-toscrape", "max_pages": 2}'
```

CLI equivalent:

```bash
python -m app.cli sources
python -m app.cli scrape --source books-toscrape --pages 2
python -m app.cli scrape --source books-toscrape --pages 2 --use-cache
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness probe with version and environment |
| GET | `/api/v1/sources` | Registered sources and the fields they extract |
| POST | `/api/v1/scrape` | Run a scrape job and persist the output |
| GET | `/api/v1/runs` | Recent run summaries (`?limit=20`) |
| GET | `/api/v1/runs/{run_id}` | One run summary |

`POST /api/v1/scrape` body:

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `source_key` | string | `books-toscrape` | Must be a registered source |
| `max_pages` | integer | `3` | Capped by `APP_MAX_PAGES_LIMIT` |
| `use_cache` | boolean | `false` | Re-parse HTML already stored in `data/raw` |

Errors: `404` for an unknown source or run id, `400` when `max_pages` exceeds the
configured limit, `502` when the site cannot be reached.

## Output layout

```
data/
├── raw/
│   └── books-toscrape/
│       └── page-001.html          # original HTML, one file per page
└── runs/
    └── 20261116T040430-bbc88f/
        ├── items.jsonl            # one JSON object per record
        └── summary.json           # counters, duration, errors, 3 sample items
```

`items.jsonl` is newline-delimited JSON: streaming friendly, append friendly, and easy
to load with `pandas.read_json(path, lines=True)` in a later iteration.

## Project structure

```
web-scraping-data-platform/
├── app/
│   ├── main.py                    # FastAPI application and lifespan
│   ├── cli.py                     # `python -m app.cli ...`
│   ├── deps.py                    # Dependency providers (service caching)
│   ├── api/v1/
│   │   ├── router.py              # Versioned API router
│   │   └── endpoints/
│   │       ├── health.py          # GET /health
│   │       └── scrape.py          # Sources and scrape-run endpoints
│   ├── core/
│   │   ├── config.py              # Environment-driven settings
│   │   └── logging.py             # Structured stdout logging
│   ├── scrapers/
│   │   ├── base.py                # BaseScraper + ScrapeOutcome
│   │   ├── fetcher.py             # robots.txt, throttling, retries, HTML cache
│   │   ├── books_toscrape.py      # Demo source implementation
│   │   └── registry.py            # Source registry
│   ├── schemas/scrape.py          # Request / response models
│   └── services/scrape_service.py # Orchestration and run persistence
├── tests/
│   ├── fixtures/books_page_1.html # Static page used by parser tests
│   ├── fakes.py                   # FakeFetcher test double
│   ├── test_books_toscrape.py
│   ├── test_scrape_service.py
│   └── test_api.py
├── .env.example
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
└── ruff.toml
```

## Configuration

Every setting can be provided as an environment variable with the `APP_` prefix, or in
`.env` (see `.env.example`). Defaults live in `app/core/config.py`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_ENVIRONMENT` | `development` | Reported by `/health` |
| `APP_LOG_LEVEL` | `INFO` | Root logger level |
| `APP_USER_AGENT` | project UA string | Identifies the crawler |
| `APP_REQUEST_TIMEOUT_SECONDS` | `15` | Per-request timeout |
| `APP_MAX_RETRIES` | `3` | Attempts per URL |
| `APP_RETRY_BACKOFF_SECONDS` | `1.0` | First backoff, doubled per retry |
| `APP_REQUEST_DELAY_SECONDS` | `0.5` | Minimum gap between requests to one host |
| `APP_RESPECT_ROBOTS_TXT` | `true` | Enforce robots.txt rules |
| `APP_DEFAULT_MAX_PAGES` | `3` | CLI default when `--pages` is omitted |
| `APP_MAX_PAGES_LIMIT` | `20` | Hard cap for API and CLI |
| `APP_DATA_DIR` | `<repo>/data` | Root of raw data, runs and exports |

## Tests and quality checks

```bash
pytest
ruff check .
ruff format --check .
```

The suite never touches the network: the parser runs against a saved HTML fixture and
the service/API tests use a fake fetcher or a stub service.

## Adding a new source

1. Create `app/scrapers/<site>.py` with a `BaseScraper` subclass that implements
   `scrape(max_pages, use_cache=False)` and declares `source_key`, `display_name`,
   `description`, `base_url` and `record_fields`.
2. Register the class in `app/scrapers/registry.py`.
3. Add a static HTML fixture and a parser test; the API and CLI expose the source
   automatically.

## Ethical scraping

This project only ships a source explicitly published for scraping practice. When you
add a real site: read its terms, keep `robots.txt` enforcement on, leave the throttle at
a polite value, identify the crawler in the user agent, and prefer incremental updates
over full re-crawls. The raw HTML archive also makes audits possible after the fact.

## Roadmap

| Iteration | Scope | Status |
| --- | --- | --- |
| 1 | App skeleton, HTTP fetcher, BeautifulSoup scraper, run persistence, API + CLI, tests | Done |
| 2 | Playwright for JavaScript-rendered pages, selector configuration, screenshots | Next |
| 3 | SQLite persistence (SQLAlchemy 2.0), fingerprint-based de-duplication, query API | Planned |
| 4 | CSV / Excel import with column mapping and a validation report | Planned |
| 5 | Cleaning pipeline: price/date normalisation, whitespace, fuzzy duplicate detection | Planned |
| 6 | Styled Excel report generation (summary sheet + data sheet + charts) | Planned |
| 7 | Scheduled incremental collection with APScheduler and job history | Planned |
| 8 | Docker image, GitHub Actions CI, demo dashboard page, portfolio write-up | Planned |

## License

MIT
