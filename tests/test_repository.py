"""Repository tests: de-duplication, filtering, pagination and counts."""

from pathlib import Path

from app.core.config import Settings
from app.db.repository import ItemRepository
from app.services.fingerprint import build_fingerprint

BOOK_FIELDS = ("title", "product_url")

BOOKS = [
    {"title": "A Light in the Attic", "price": 51.77, "product_url": "https://books/1"},
    {"title": "Tipping the Velvet", "price": 53.74, "product_url": "https://books/2"},
]
QUOTES = [{"quote": "Change your thoughts.", "author": "Albert Einstein"}]


def make_repo(tmp_path: Path) -> ItemRepository:
    return ItemRepository(Settings(data_dir=tmp_path, _env_file=None))


def test_add_items_is_idempotent(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    first = repo.add_items("books-toscrape", BOOKS, fingerprint_fields=BOOK_FIELDS, run_id="run-1")
    second = repo.add_items("books-toscrape", BOOKS, fingerprint_fields=BOOK_FIELDS, run_id="run-2")

    assert first == (2, 0)
    assert second == (0, 2)
    total, rows = repo.list_items()
    assert total == 2
    # The first run keeps the row and its run id; duplicates do not overwrite it.
    assert rows[0].run_id == "run-1"


def test_duplicate_ignores_volatile_fields(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    repo.add_items("books-toscrape", BOOKS, fingerprint_fields=BOOK_FIELDS, run_id="run-1")

    changed = [dict(BOOKS[0], price=99.99, availability="Out of stock")]
    inserted, duplicated = repo.add_items(
        "books-toscrape", changed, fingerprint_fields=BOOK_FIELDS, run_id="run-2"
    )

    assert (inserted, duplicated) == (0, 1)


def test_fingerprint_normalizes_case_and_whitespace() -> None:
    left = build_fingerprint(
        {"title": "  A  Light ", "product_url": "HTTPS://Books/1"}, BOOK_FIELDS
    )
    right = build_fingerprint({"title": "a light", "product_url": "https://books/1"}, BOOK_FIELDS)

    assert left == right
    assert left != build_fingerprint(
        {"title": "A Light", "product_url": "https://books/2"}, BOOK_FIELDS
    )


def test_list_items_filters_and_paginates(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    repo.add_items("books-toscrape", BOOKS, fingerprint_fields=BOOK_FIELDS, run_id="run-1")
    repo.add_items(
        "quotes-static",
        QUOTES,
        fingerprint_fields=("quote", "author"),
        run_id="run-1",
    )

    total, rows = repo.list_items(source_key="books-toscrape", limit=1, offset=1)
    assert total == 2
    assert [row.data["title"] for row in rows] == ["Tipping the Velvet"]

    total, rows = repo.list_items(search="ALBERT")
    assert total == 1
    assert rows[0].source_key == "quotes-static"


def test_source_counts_groups_by_source(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    repo.add_items("books-toscrape", BOOKS, fingerprint_fields=BOOK_FIELDS, run_id="run-1")
    repo.add_items("quotes-static", QUOTES, fingerprint_fields=("quote", "author"), run_id="run-1")

    assert repo.source_counts() == [("books-toscrape", 2), ("quotes-static", 1)]
