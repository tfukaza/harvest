"""SQLite helpers for infrastructure storage backends."""

from __future__ import annotations

from pathlib import Path


def ensure_sqlite_directory(database_url: str) -> None:
    """Ensure the directory for a file-backed SQLite database exists.

    Args:
        database_url: SQLAlchemy database URL.
    """
    if not database_url.startswith("sqlite:///"):
        return

    raw_path = database_url.removeprefix("sqlite:///")
    if raw_path == ":memory:":
        return

    database_path = Path(raw_path)
    if database_path.parent != Path():
        database_path.parent.mkdir(parents=True, exist_ok=True)
