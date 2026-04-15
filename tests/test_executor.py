"""Tests for :mod:`queryforge.executor`."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from queryforge.executor import Executor, schema_from_sqlite


@pytest.fixture()
def sample_db(tmp_path: Path) -> Path:
    db = tmp_path / "shop.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER
            );
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                total REAL
            );
            INSERT INTO customers (name, age) VALUES ('Alice', 30), ('Bob', 25), ('Carol', 42);
            INSERT INTO orders (customer_id, total) VALUES (1, 99.5), (1, 10.0), (2, 500.0);
            CREATE VIEW big_orders AS
                SELECT id, total FROM orders WHERE total > 100;
            """
        )
    return db


def test_schema_from_sqlite_includes_tables_and_views(sample_db: Path) -> None:
    schema = schema_from_sqlite(sample_db)
    assert set(schema.tables) == {"customers", "orders", "big_orders"}
    assert schema.tables["customers"] == ["id", "name", "age"]
    assert schema.tables["orders"] == ["id", "customer_id", "total"]


def test_schema_from_sqlite_skips_internal_tables(sample_db: Path) -> None:
    schema = schema_from_sqlite(sample_db)
    assert not any(name.startswith("sqlite_") for name in schema.tables)


def test_schema_from_sqlite_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        schema_from_sqlite(tmp_path / "nope.sqlite")


def test_executor_runs_select(sample_db: Path) -> None:
    result = Executor(sample_db).run("SELECT name, age FROM customers ORDER BY age")
    assert result.columns == ["name", "age"]
    assert result.rows == [("Bob", 25), ("Alice", 30), ("Carol", 42)]
    assert result.sql.endswith("LIMIT 100")


def test_executor_respects_explicit_limit(sample_db: Path) -> None:
    result = Executor(sample_db).run("SELECT name FROM customers LIMIT 1")
    # We must not double-append LIMIT.
    assert result.sql.lower().count("limit") == 1
    assert len(result) == 1


def test_executor_readonly_blocks_writes(sample_db: Path) -> None:
    with pytest.raises(sqlite3.OperationalError):
        Executor(sample_db).run("INSERT INTO customers (name) VALUES ('x')")


def test_executor_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Executor(tmp_path / "nope.sqlite")
