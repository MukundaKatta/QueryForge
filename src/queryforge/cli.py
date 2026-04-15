"""Command-line interface for QueryForge.

Three commands:

* ``queryforge translate "<question>" --db path/to.sqlite``
  Print the generated SQL. If ``--db`` is given, auto-introspect the
  schema from that file. Otherwise accept ``--schema`` JSON.

* ``queryforge run "<question>" --db path/to.sqlite``
  Translate *and* execute, printing a compact results table.

* ``queryforge repl --db path/to.sqlite``
  Interactive loop: type a question, get SQL + results, repeat.

The CLI uses only stdlib — no ``click`` or ``typer`` dependency — so
QueryForge stays "inspectable" as the tagline promises.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from queryforge.config import Config
from queryforge.core import QueryEngine, Schema
from queryforge.executor import Executor, QueryResult, schema_from_sqlite


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_schema(args: argparse.Namespace) -> Schema:
    """Load a Schema from either --db (preferred) or --schema JSON."""
    if getattr(args, "db", None):
        return schema_from_sqlite(args.db)
    if getattr(args, "schema", None):
        path = Path(args.schema)
        data = json.loads(path.read_text(encoding="utf-8"))
        return Schema.from_dict(data)
    raise SystemExit(
        "error: provide either --db <sqlite-file> or --schema <schema.json>"
    )


def _format_table(result: QueryResult, *, max_col_width: int = 40) -> str:
    """Render ``result`` as a monospace ASCII table."""
    if not result.columns:
        return "(no columns)"

    rows = [tuple(str(v) if v is not None else "NULL" for v in row) for row in result.rows]
    widths = [len(c) for c in result.columns]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = min(max(widths[i], len(cell)), max_col_width)

    def _fmt_row(cells: Sequence[str]) -> str:
        return "│ " + " │ ".join(c[:w].ljust(w) for c, w in zip(cells, widths)) + " │"

    sep = "┼".join("─" * (w + 2) for w in widths)
    lines = [
        "┌" + "┬".join("─" * (w + 2) for w in widths) + "┐",
        _fmt_row(result.columns),
        "├" + sep + "┤",
        *(_fmt_row(r) for r in rows),
        "└" + "┴".join("─" * (w + 2) for w in widths) + "┘",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def _cmd_translate(args: argparse.Namespace) -> int:
    schema = _resolve_schema(args)
    engine = QueryEngine(schema, Config(validate=not args.no_validate))
    try:
        explanation = engine.explain(args.question)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.explain:
        print(explanation.render())
    else:
        print(explanation.sql)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    if not args.db:
        print("error: `run` requires --db <sqlite-file>", file=sys.stderr)
        return 2
    schema = _resolve_schema(args)
    engine = QueryEngine(schema, Config(validate=not args.no_validate))
    try:
        sql = engine.translate(args.question)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"-- {sql}")
    executor = Executor(args.db)
    try:
        result = executor.run(sql, limit=args.limit)
    except Exception as exc:  # sqlite3.OperationalError, etc.
        print(f"error: {exc}", file=sys.stderr)
        return 3
    print(_format_table(result))
    return 0


def _cmd_repl(args: argparse.Namespace) -> int:
    if not args.db:
        print("error: `repl` requires --db <sqlite-file>", file=sys.stderr)
        return 2
    schema = _resolve_schema(args)
    engine = QueryEngine(schema, Config(validate=not args.no_validate))
    executor = Executor(args.db)

    tables = ", ".join(sorted(schema.tables.keys())) or "(none)"
    print(f"QueryForge REPL — tables: {tables}")
    print("Type a question in natural language, or :q to quit, :tables to list tables.")
    while True:
        try:
            question = input("› ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            continue
        if question in (":q", ":quit", ":exit"):
            return 0
        if question in (":tables", ":schema"):
            for name, cols in sorted(schema.tables.items()):
                print(f"  {name}({', '.join(cols)})")
            continue
        try:
            sql = engine.translate(question)
        except ValueError as exc:
            print(f"  error: {exc}")
            continue
        print(f"  -- {sql}")
        try:
            result = executor.run(sql, limit=args.limit)
        except Exception as exc:
            print(f"  error: {exc}")
            continue
        print(_format_table(result))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="queryforge",
        description="Natural language to SQL — no LLM required.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--db", help="SQLite file to introspect (also used for `run`/`repl`).")
        p.add_argument("--schema", help="Path to schema JSON ({table: [cols]}).")
        p.add_argument("--no-validate", action="store_true", help="Skip SQL safety validation.")
        p.add_argument("--limit", type=int, default=100, help="Row cap for execution (default 100).")

    p_trans = sub.add_parser("translate", help="Translate a question to SQL and print it.")
    p_trans.add_argument("question")
    p_trans.add_argument("--explain", action="store_true",
                         help="Print the full pipeline trace (tokens, intent, entities) before the SQL.")
    _common(p_trans)
    p_trans.set_defaults(func=_cmd_translate)

    p_run = sub.add_parser("run", help="Translate and execute against --db, printing rows.")
    p_run.add_argument("question")
    _common(p_run)
    p_run.set_defaults(func=_cmd_run)

    p_repl = sub.add_parser("repl", help="Interactive REPL: type questions, see rows.")
    _common(p_repl)
    p_repl.set_defaults(func=_cmd_repl)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
