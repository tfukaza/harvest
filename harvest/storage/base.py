"""Infrastructure-only storage primitives for Harvest."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
import sqlalchemy
from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import Integer

from harvest.storage.sqlite import ensure_sqlite_directory


class StorageRecord(DeclarativeBase):
    """Base declarative model used by schema-specific storage tables."""


@dataclass(frozen=True)
class TableRegistration:
    """Metadata for a registered persisted table.

    Attributes:
        model: SQLAlchemy declarative model.
        unique_fields: Logical key columns used for upsert behavior.
        persisted_columns: Stored column names excluding generated identifiers.
    """

    model: type[StorageRecord]
    unique_fields: tuple[str, ...]
    persisted_columns: tuple[str, ...]


class FlexibleStorage:
    """Generic storage engine that supports SQLite and CSV persistence.

    The engine only knows about registered table metadata and row dictionaries.
    Schema-specific wrappers define the models and storage semantics above it.
    """

    def __init__(
        self,
        *,
        database_url: str | None = None,
        csv_directory: str | Path | None = None,
    ) -> None:
        """Initialize the storage engine.

        Args:
            database_url: SQLAlchemy URL for SQLite-backed persistence.
            csv_directory: Directory for CSV-backed persistence.

        Raises:
            ValueError: If neither or both backends are configured.
        """
        if (database_url is None) == (csv_directory is None):
            raise ValueError("Configure exactly one FlexibleStorage backend")

        self._registrations: dict[str, TableRegistration] = {}
        self._database_url = database_url
        self._csv_directory = Path(csv_directory) if csv_directory is not None else None
        self.db_engine: sqlalchemy.Engine | None = None

        if database_url is not None:
            ensure_sqlite_directory(database_url)
            self.db_engine = sqlalchemy.create_engine(database_url)
        else:
            assert self._csv_directory is not None
            self._csv_directory.mkdir(parents=True, exist_ok=True)

    @property
    def database_url(self) -> str:
        """Return a backend location string for diagnostics."""
        if self._database_url is not None:
            return self._database_url
        assert self._csv_directory is not None
        return f"csv:///{self._csv_directory}"

    @property
    def is_csv_backend(self) -> bool:
        """Return whether this engine persists tables as CSV files."""
        return self._csv_directory is not None

    def register_table(
        self,
        model: type[StorageRecord],
        *,
        unique_fields: tuple[str, ...] | None = None,
    ) -> None:
        """Register a table for persistence.

        Args:
            model: Declarative model representing the table schema.
            unique_fields: Explicit logical key columns for upsert behavior.
        """
        registration = TableRegistration(
            model=model,
            unique_fields=unique_fields or self._infer_unique_fields(model),
            persisted_columns=self._persisted_columns(model),
        )
        self._registrations[model.__tablename__] = registration

        if self.db_engine is not None:
            model.metadata.create_all(self.db_engine, tables=[model.__table__])

    def empty_frame(self, model: type[StorageRecord]) -> pl.DataFrame:
        """Create an empty frame using the registered persisted columns."""
        registration = self._get_registration(model)
        return pl.DataFrame(schema=list(registration.persisted_columns))

    def upsert_rows(self, model: type[StorageRecord], rows: list[dict[str, Any]]) -> None:
        """Insert or update rows for a registered table."""
        if not rows:
            return

        registration = self._get_registration(model)
        normalized_rows = [self._normalize_row(row, registration.persisted_columns) for row in rows]

        if self.db_engine is not None:
            statement = insert(model).values(normalized_rows)
            if registration.unique_fields:
                update_columns = {
                    column: getattr(statement.excluded, column)
                    for column in registration.persisted_columns
                    if column not in registration.unique_fields
                }
                if update_columns:
                    statement = statement.on_conflict_do_update(
                        index_elements=list(registration.unique_fields),
                        set_=update_columns,
                    )
                else:
                    statement = statement.on_conflict_do_nothing(index_elements=list(registration.unique_fields))

            with Session(self.db_engine) as session:
                session.execute(statement)
                session.commit()
            return

        frame = self._read_csv_frame(model)
        incoming = pl.DataFrame(normalized_rows)
        combined = incoming if frame.is_empty() else pl.concat([frame, incoming], how="diagonal_relaxed")
        if registration.unique_fields:
            combined = combined.unique(subset=list(registration.unique_fields), keep="last", maintain_order=True)
        combined = self._ensure_column_order(combined, registration.persisted_columns)
        combined.write_csv(self._csv_path(model))

    def fetch_rows(
        self,
        model: type[StorageRecord],
        *,
        filters: dict[str, Any] | None = None,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
        timestamp_field: str = "timestamp",
        order_by: list[tuple[str, bool]] | None = None,
    ) -> pl.DataFrame:
        """Fetch rows from a registered table as a Polars dataframe."""
        registration = self._get_registration(model)
        order_by = order_by or []

        if self.db_engine is not None:
            statement = select(model.__table__)
            for field_name, value in (filters or {}).items():
                statement = statement.where(model.__table__.c[field_name] == value)
            if start is not None:
                statement = statement.where(model.__table__.c[timestamp_field] >= start)
            if end is not None:
                statement = statement.where(model.__table__.c[timestamp_field] <= end)
            for field_name, ascending in order_by:
                column = model.__table__.c[field_name]
                statement = statement.order_by(column.asc() if ascending else column.desc())

            with Session(self.db_engine) as session:
                rows = [dict(row) for row in session.execute(statement).mappings().all()]

            if not rows:
                return self.empty_frame(model)

            frame = pl.DataFrame(rows)
            return self._finalize_frame(frame, registration.persisted_columns)

        frame = self._read_csv_frame(model)
        if frame.is_empty():
            return frame

        for field_name, value in (filters or {}).items():
            frame = frame.filter(pl.col(field_name) == value)
        if start is not None and timestamp_field in frame.columns:
            frame = frame.filter(pl.col(timestamp_field) >= pl.lit(start))
        if end is not None and timestamp_field in frame.columns:
            frame = frame.filter(pl.col(timestamp_field) <= pl.lit(end))
        if order_by:
            frame = frame.sort([field for field, _ in order_by], descending=[not ascending for _, ascending in order_by])

        return self._finalize_frame(frame, registration.persisted_columns)

    def delete_before(
        self,
        model: type[StorageRecord],
        *,
        cutoff: dt.datetime,
        timestamp_field: str = "timestamp",
        filters: dict[str, Any] | None = None,
    ) -> None:
        """Delete rows older than or equal to a cutoff timestamp."""
        self.delete_rows(
            model,
            filters=filters,
            before=cutoff,
            timestamp_field=timestamp_field,
        )

    def delete_rows(
        self,
        model: type[StorageRecord],
        *,
        filters: dict[str, Any] | None = None,
        before: dt.datetime | None = None,
        timestamp_field: str = "timestamp",
    ) -> None:
        """Delete rows matching simple equality and timestamp predicates."""
        registration = self._get_registration(model)

        if self.db_engine is not None:
            statement = delete(model.__table__)
            for field_name, value in (filters or {}).items():
                statement = statement.where(model.__table__.c[field_name] == value)
            if before is not None:
                statement = statement.where(model.__table__.c[timestamp_field] <= before)

            with Session(self.db_engine) as session:
                session.execute(statement)
                session.commit()
            return

        frame = self._read_csv_frame(model)
        if frame.is_empty():
            return

        keep_filter = pl.lit(True)
        for field_name, value in (filters or {}).items():
            keep_filter = keep_filter & (pl.col(field_name) == value)
        if before is not None and timestamp_field in frame.columns:
            keep_filter = keep_filter & (pl.col(timestamp_field) <= pl.lit(before))

        remaining = frame.filter(~keep_filter)
        remaining = self._ensure_column_order(remaining, registration.persisted_columns)
        remaining.write_csv(self._csv_path(model))

    def _get_registration(self, model: type[StorageRecord]) -> TableRegistration:
        try:
            return self._registrations[model.__tablename__]
        except KeyError as exc:
            raise ValueError(f"Unregistered table: {model.__tablename__}") from exc

    def _infer_unique_fields(self, model: type[StorageRecord]) -> tuple[str, ...]:
        for constraint in model.__table__.constraints:
            if isinstance(constraint, sqlalchemy.UniqueConstraint):
                return tuple(column.name for column in constraint.columns)

        primary_keys = [column.name for column in model.__table__.primary_key.columns if not self._is_generated_identifier(column)]
        return tuple(primary_keys)

    def _persisted_columns(self, model: type[StorageRecord]) -> tuple[str, ...]:
        return tuple(
            column.name for column in model.__table__.columns if not self._is_generated_identifier(column)
        )

    def _is_generated_identifier(self, column: Column[Any]) -> bool:
        return bool(column.primary_key and column.autoincrement and isinstance(column.type, Integer))

    def _normalize_row(self, row: dict[str, Any], columns: tuple[str, ...]) -> dict[str, Any]:
        return {column: row[column] for column in columns if column in row}

    def _csv_path(self, model: type[StorageRecord]) -> Path:
        assert self._csv_directory is not None
        return self._csv_directory / f"{model.__tablename__}.csv"

    def _read_csv_frame(self, model: type[StorageRecord]) -> pl.DataFrame:
        csv_path = self._csv_path(model)
        if not csv_path.exists():
            return self.empty_frame(model)

        frame = pl.read_csv(csv_path, try_parse_dates=True)
        registration = self._get_registration(model)
        return self._ensure_column_order(frame, registration.persisted_columns)

    def _ensure_column_order(self, frame: pl.DataFrame, columns: tuple[str, ...]) -> pl.DataFrame:
        current = frame
        for column in columns:
            if column not in current.columns:
                current = current.with_columns(pl.lit(None).alias(column))
        return current.select(list(columns))

    def _finalize_frame(self, frame: pl.DataFrame, columns: tuple[str, ...]) -> pl.DataFrame:
        return self._ensure_column_order(frame, columns)


class CSVStorage(FlexibleStorage):
    """CSV-backed infrastructure storage for local debugging and tests."""

    def __init__(self, save_dir: str = "data") -> None:
        """Initialize the CSV-backed storage engine.

        Args:
            save_dir: Directory where CSV files will be written.
        """
        super().__init__(csv_directory=save_dir)
