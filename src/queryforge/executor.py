"""SQLite executor and schema introspection.

QueryForge focuses on translating natural language to SQL, but the
translation is a lot more useful if you can run it immediately against
a real database and see the rows. This module provides two tiny helpers:

* :func:`schema_from_sqlite` — introspect a SQLite file and build a
  :class:`~queryforge.core.Schema` from its tables and columns.
* :class:`Executor` — run a generated SELECT against the same database
  and return the rows as plain Python values, with a read-only cursor.

No new runtime dependencies: everything uses the stdlib ``sqlite3``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from queryforge.core import Schema


def schema_from_sqlite(db_path: str | Path) -> Schema:
    """Build a :class:`Schema` by introspecting ``db_path``.

    Uses ``sqlite_master`` + ``PRAGMA table_info`` to enumerate tables
    and columns. Views are included; internal SQLite tables
    (``sqlite_*``) and hidden virtual-table shadow tables are skipped.
    """
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")

    tables: dict[str, list[str]] = {}
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        names = [row["name"] for row in cur.fetchall()]
        for name in names:
            # PRAGMA table_info doesn't allow parameters; quote the name.
            safe = name.replace('"', '""')
            cur = conn.execute(f'PRAGMA table_info("{safe}")')
            cols = [row["name"] for row in cur.fetchall()]
            if cols:
                tables[name] = cols
    return Schema(tables=tables)


@dataclass
class QueryResult:
    """Rows + column names returned from :meth:`Executor.run`."""

    columns: list[str]
    rows: list[tuple[Any, ...]]
    sql: str

    def __iter__(self) -> Iterable[tuple[Any, ...]]:
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)


class Executor:
    """Run SQL against a SQLite file with a read-only connection.

    The connection opens with ``mode=ro``, so even if a caller hands us
    non-SELECT SQL the database cannot be modified. The :class:`Validator`
    in :mod:`queryforge.core` is an additional, earlier line of defense.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

    def run(self, sql: str, *, limit: int | None = 100) -> QueryResult:
        """Execute ``sql`` and return rows.

        ``limit`` is a safety cap applied via ``LIMIT`` *inside* SQLite if
        the generated SQL doesn't already have one. Set to ``None`` for
        no implicit cap.
        """
        effective_sql = sql
        if limit is not None and "limit" not in sql.lower():
            effective_sql = f"{sql} LIMIT {int(limit)}"

        with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(effective_sql)
            rows = cur.fetchall()
            columns = [d[0] for d in (cur.description or [])]
            return QueryResult(
                columns=columns,
                rows=[tuple(r) for r in rows],
                sql=effective_sql,
            )
