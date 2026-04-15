"""Tests for :mod:`queryforge.cli`."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from queryforge.cli import main


@pytest.fixture()
def shop_db(tmp_path: Path) -> Path:
    db = tmp_path / "shop.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, age INTEGER);
            INSERT INTO customers (name, age) VALUES ('Alice', 30), ('Bob', 25);
            """
        )
    return db


def test_translate_prints_sql(shop_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["translate", "show all customers", "--db", str(shop_db)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.upper().startswith("SELECT")
    assert "customers" in out


def test_translate_with_schema_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps({"products": ["id", "name", "price"]}))
    rc = main(["translate", "list products", "--schema", str(schema_path)])
    assert rc == 0
    assert "products" in capsys.readouterr().out


def test_translate_requires_schema_source(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        main(["translate", "anything"])


def test_run_executes_and_prints_table(
    shop_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["run", "show all customers", "--db", str(shop_db)])
    assert rc == 0
    out = capsys.readouterr().out
    # Generated SQL is echoed as a comment, and the table contains the data.
    assert "-- SELECT" in out
    assert "Alice" in out
    assert "Bob" in out


def test_run_needs_db(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["run", "show customers"])
    assert rc == 2
    assert "requires --db" in capsys.readouterr().err


def test_translate_reports_validation_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A question that mentions no known table should surface a clean error,
    # not a traceback.
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps({"products": ["id", "name"]}))
    rc = main(["translate", "hello world", "--schema", str(schema_path)])
    assert rc == 2
    assert "error" in capsys.readouterr().err.lower()
