"""Deterministic record identity used for de-duplication.

A site can change prices, availability or timestamps between two crawls; those fields
must not create a second row. The fingerprint is built only from the fields a scraper
declares as its identity (for example title + product URL) and normalised so that
casing and whitespace differences do not matter.
"""

from __future__ import annotations

import hashlib
from typing import Any

# Separator unlikely to appear inside a real value, so field boundaries stay clear.
_FIELD_SEPARATOR = "\x1f"


def normalize_value(value: Any) -> str:
    """Collapse a scalar or list into a stable, case-insensitive string."""
    if value is None:
        return ""
    if isinstance(value, list | tuple | set):
        return "|".join(normalize_value(item) for item in value)
    return " ".join(str(value).casefold().split())


def build_fingerprint(record: dict[str, Any], fields: tuple[str, ...]) -> str:
    """Return the SHA-256 identity of ``record`` using ``fields``."""
    payload = _FIELD_SEPARATOR.join(
        f"{field}={normalize_value(record.get(field))}" for field in fields
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
