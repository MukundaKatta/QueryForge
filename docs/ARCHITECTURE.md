# QueryForge Architecture

## Overview

QueryForge converts natural language questions into SQL queries using a pipeline of rule-based components. No machine learning model or LLM API is required for common query patterns.

## Pipeline

```
Natural Language Input
        |
        v
  +-----------+
  | Tokenizer |  Split text into normalized tokens, remove stop words
  +-----------+
        |
        v
  +------------------+
  | IntentClassifier |  Detect query type (SELECT, COUNT, AVG, etc.)
  +------------------+  and modifiers (WHERE, JOIN, GROUP BY, ORDER BY)
        |
        v
  +--------------+
  | SchemaMapper |  Map tokens to tables, columns, operators, and values
  +--------------+
        |
        v
  +------------+
  | SQLBuilder |  Assemble final SQL string from structured components
  +------------+
        |
        v
  +-----------+
  | Validator |  Safety checks (no DROP/DELETE, balanced parens, etc.)
  +-----------+
        |
        v
    SQL Output
```

## Components

### Schema
Holds the database schema as a dict of `table -> [columns]`. Provides lookup methods for finding tables by name, columns across tables, and heuristic foreign-key detection for JOIN clauses.

### Tokenizer
Lowercases input, removes punctuation, splits on whitespace, and filters out common English stop words that carry no SQL-relevant meaning.

### IntentClassifier
Uses keyword sets to determine:
- **Action**: SELECT, COUNT, AVG, SUM, MAX, MIN
- **Modifiers**: WHERE, JOIN, GROUP BY, ORDER BY
- **Direction**: ASC / DESC
- **Limit**: extracted from "top N" patterns

### SchemaMapper
Maps cleaned tokens back to schema entities:
- Matches tokens to table names (tries singular/plural variants)
- Matches tokens to column names
- Extracts numeric values and comparison operators
- Infers aggregate and group-by columns

### SQLBuilder
Takes the structured `Intent` and `MappedEntities` and assembles a SQL string with proper clause ordering.

### Validator
Rejects anything that is not a SELECT statement. Checks for dangerous keywords (DROP, DELETE, ALTER, etc.) and basic syntax issues like unbalanced parentheses.

## Design Decisions

1. **Rule-based first**: Covers 80% of common analytical questions without API costs or latency.
2. **Schema awareness**: The engine never guesses table/column names; it only uses what exists in the provided schema.
3. **Safety by default**: Validation is on by default and only SELECT queries are permitted.
4. **Extensible**: The pipeline is modular; any component can be replaced or extended (e.g., swap in an LLM-based IntentClassifier for complex queries).
