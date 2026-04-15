# QueryForge

**Natural language → SQL, with zero LLM calls.**

```
$ queryforge run "top 5 customers by total order value" --db shop.sqlite
-- SELECT customers.* FROM customers JOIN orders ON customers.id = orders.customer_id ORDER BY orders.total DESC LIMIT 5
┌────┬─────────┬─────┐
│ id │ name    │ age │
├────┼─────────┼─────┤
│ 3  │ Carol   │ 42  │
│ 1  │ Alice   │ 30  │
│ 2  │ Bob     │ 25  │
└────┴─────────┴─────┘
```

QueryForge translates plain-English questions into safe, read-only SQL by
walking a rule-based pipeline: tokenize → classify intent → map to schema →
assemble SQL → validate. No API keys. No round-trips. No surprise `DROP TABLE`.

The entire translation layer is **~400 lines of Python** you can read in one
sitting — and the executor gives you results against any SQLite database
without writing a single query by hand.

## Why

LLM-based NL-to-SQL works, but it:

- Costs money per query, so you can't embed it in a dashboard that fires every second.
- Is non-deterministic — the same question can produce different SQL tomorrow.
- Is a black box — when it gets the JOIN wrong you can't debug the pipeline.
- Is a security concern — prompt injection in a user-supplied question can coax `DELETE FROM`.

QueryForge aims for the 80% of natural-language questions that fit obvious
patterns (selects, counts, aggregates, simple joins, top-N) and handles them
**deterministically**, **offline**, and **transparently**.

## Install

```bash
pip install -e .
# or, once published to PyPI:
pip install queryforge
```

Python ≥ 3.9. No runtime dependencies beyond the standard library.

## Quick start

### 1. Translate a question

```bash
queryforge translate "how many customers over 30" --db shop.sqlite
# SELECT COUNT(*) FROM customers WHERE customers.age > 30
```

### 2. Translate *and* execute

```bash
queryforge run "average order total per customer" --db shop.sqlite
-- SELECT AVG(orders.total) FROM orders JOIN customers ON orders.customer_id = customers.id GROUP BY orders.customer_id
┌──────────────────┐
│ AVG(orders.total)│
├──────────────────┤
│ 54.75            │
│ 500.0            │
└──────────────────┘
```

### 3. Interactive REPL

```bash
queryforge repl --db shop.sqlite
QueryForge REPL — tables: customers, orders
Type a question in natural language, or :q to quit, :tables to list tables.
› top 3 orders by total
  -- SELECT orders.* FROM orders ORDER BY orders.total DESC LIMIT 3
┌────┬─────────────┬────────┐
│ id │ customer_id │ total  │
├────┼─────────────┼────────┤
│ 3  │ 2           │ 500.0  │
│ 1  │ 1           │ 99.5   │
│ 2  │ 1           │ 10.0   │
└────┴─────────────┴────────┘
› :q
```

## Python API

```python
from queryforge import QueryEngine, schema_from_sqlite, Executor

schema = schema_from_sqlite("shop.sqlite")
engine = QueryEngine(schema)

sql = engine.translate("customers over 30")
# SELECT customers.* FROM customers WHERE customers.age > 30

result = Executor("shop.sqlite").run(sql)
for row in result:
    print(row)
```

Or hand-roll a schema:

```python
from queryforge import QueryEngine, Schema

schema = Schema.from_dict({
    "customers": ["id", "name", "age"],
    "orders":    ["id", "customer_id", "total"],
})
engine = QueryEngine(schema)
print(engine.translate("top 5 orders"))
```

## What it understands

| Intent        | Trigger words                                   | Example                                      |
| ------------- | ----------------------------------------------- | -------------------------------------------- |
| `SELECT`      | (default)                                       | *"show me the customers"*                    |
| `COUNT(*)`    | count, how many, number of                      | *"how many orders"*                          |
| `AVG`         | average, avg, mean                              | *"average order total"*                      |
| `SUM`         | sum, total                                      | *"total revenue per customer"*               |
| `MAX` / `MIN` | max, highest, largest / min, lowest, cheapest   | *"most expensive order"* / *"cheapest item"* |
| `WHERE`       | over, above, under, below, equal, between       | *"customers over 30"*                        |
| `JOIN`        | mention two schema tables; `_id` FK detect      | *"orders for Alice"*                         |
| `GROUP BY`    | per, each, grouped by                           | *"total per customer"*                       |
| `ORDER BY`    | order, sort, top, highest                       | *"top 10 orders"*                            |
| `LIMIT`       | `top N`                                         | *"top 5"*                                    |

## Safety

- **Read-only connection.** The executor opens every SQLite connection with
  `mode=ro`, so even a malformed translation cannot mutate the database.
- **Validator.** Rejects any SQL that isn't a plain `SELECT`, catches
  unbalanced parentheses, and bans the dangerous keywords (`DROP`, `DELETE`,
  `ALTER`, `UPDATE`, `INSERT`, `TRUNCATE`, `EXEC`, `EXECUTE`).
- **Deterministic.** The same question against the same schema always
  produces the same SQL — no stochasticity, no fallback to a cloud model.

## When it's *not* the right tool

QueryForge is great for dashboards, demo UIs, analyst shortcuts, and
agent-in-the-loop sketches. It is **not** trying to replace a real LLM
translator for open-ended questions, correlated subqueries, or window
functions. If you need those, reach for a production NL2SQL service — and
feel free to use QueryForge's `Validator` as your guardrail.

## Architecture

```
question ─► Tokenizer ─► IntentClassifier ─► SchemaMapper ─► SQLBuilder ─► Validator ─► sql
                                                 ▲
                         Schema (manual or schema_from_sqlite) ─┘
```

Every step is a tiny pure function. Swap any of them in tests, or subclass
`QueryEngine` to inject your own mapper.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest          # runs in < 1s
ruff check .
mypy src
```

## License

MIT. See [LICENSE](LICENSE).
