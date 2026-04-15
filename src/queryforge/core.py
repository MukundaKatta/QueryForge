"""Core engine for natural language to SQL conversion."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from queryforge.config import Config
from queryforge.utils import normalize_whitespace, strip_currency


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

@dataclass
class Schema:
    """Represents the database schema (tables and their columns)."""

    tables: dict[str, list[str]] = field(default_factory=dict)

    # Lookup helpers
    _col_to_tables: dict[str, list[str]] = field(
        default_factory=dict, repr=False, init=False
    )

    def __post_init__(self) -> None:
        self._build_index()

    def _build_index(self) -> None:
        self._col_to_tables = {}
        for table, cols in self.tables.items():
            for col in cols:
                self._col_to_tables.setdefault(col, []).append(table)

    @classmethod
    def from_dict(cls, d: dict[str, list[str]]) -> "Schema":
        return cls(tables=d)

    def find_table(self, name: str) -> str | None:
        """Return the table name if it exists (case-insensitive)."""
        lower_map = {t.lower(): t for t in self.tables}
        return lower_map.get(name.lower())

    def find_column(self, name: str) -> list[str]:
        """Return list of tables that contain *name* as a column."""
        lower_map = {c.lower(): c for c in self._col_to_tables}
        real = lower_map.get(name.lower())
        if real is None:
            return []
        return self._col_to_tables[real]

    def get_columns(self, table: str) -> list[str]:
        matched = self.find_table(table)
        if matched is None:
            return []
        return self.tables[matched]

    def detect_join_column(self, t1: str, t2: str) -> tuple[str, str] | None:
        """Heuristic: look for t2_id in t1 or t1_id in t2."""
        cols1 = {c.lower(): c for c in self.get_columns(t1)}
        cols2 = {c.lower(): c for c in self.get_columns(t2)}
        fk = f"{t2.rstrip('s')}_id"
        if fk in cols1:
            return (f"{t1}.{cols1[fk]}", f"{t2}.id")
        fk = f"{t1.rstrip('s')}_id"
        if fk in cols2:
            return (f"{t1}.id", f"{t2}.{cols2[fk]}")
        return None


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class Tokenizer:
    """Split natural language input into normalized tokens."""

    STOP_WORDS = frozenset(
        "a an the is are was were do does did me my i to of and in for on "
        "with that this from by at it its show get find list fetch give".split()
    )

    @staticmethod
    def tokenize(text: str) -> list[str]:
        text = text.lower().strip()
        text = re.sub(r"[?!.,;:'\"]", "", text)
        tokens = text.split()
        return tokens

    @classmethod
    def remove_stop_words(cls, tokens: list[str]) -> list[str]:
        return [t for t in tokens if t not in cls.STOP_WORDS]


# ---------------------------------------------------------------------------
# Intent Classifier
# ---------------------------------------------------------------------------

@dataclass
class Intent:
    action: str  # select, count, average, sum, max, min
    has_where: bool = False
    has_join: bool = False
    has_group_by: bool = False
    has_order_by: bool = False
    order_dir: str = "ASC"
    limit: int | None = None


class IntentClassifier:
    """Rule-based intent detection from tokens."""

    COUNT_WORDS = {"count", "how many", "number of", "total number"}
    AVG_WORDS = {"average", "avg", "mean"}
    SUM_WORDS = {"sum", "total"}
    MAX_WORDS = {"max", "maximum", "highest", "largest", "biggest", "most expensive"}
    MIN_WORDS = {"min", "minimum", "lowest", "smallest", "cheapest"}
    ORDER_WORDS = {"order", "sort", "sorted", "ordered", "ranked"}
    GROUP_WORDS = {"per", "each", "group", "grouped", "by each"}
    WHERE_SIGNALS = {
        "where", "who", "whose", "which", "over", "under", "above",
        "below", "greater", "less", "more", "fewer", "equal", "between",
        "before", "after", "named", "called", "with",
    }
    JOIN_SIGNALS = {"join", "joined", "placed", "bought", "made", "wrote", "from"}

    @classmethod
    def classify(cls, text: str, tokens: list[str]) -> Intent:
        text_lower = text.lower()
        action = "select"
        for w in cls.COUNT_WORDS:
            if w in text_lower:
                action = "count"
                break
        if action == "select":
            for w in cls.AVG_WORDS:
                if w in text_lower:
                    action = "average"
                    break
        if action == "select":
            for w in cls.SUM_WORDS:
                if w in text_lower:
                    action = "sum"
                    break
        if action == "select":
            for w in cls.MAX_WORDS:
                if w in text_lower:
                    action = "max"
                    break
        if action == "select":
            for w in cls.MIN_WORDS:
                if w in text_lower:
                    action = "min"
                    break

        has_where = any(t in cls.WHERE_SIGNALS for t in tokens)
        has_join = any(t in cls.JOIN_SIGNALS for t in tokens)
        has_group = any(t in cls.GROUP_WORDS for t in tokens)
        has_order = any(t in cls.ORDER_WORDS for t in tokens)
        order_dir = "DESC" if any(t in tokens for t in ("desc", "descending", "top", "highest", "largest")) else "ASC"

        limit: int | None = None
        m = re.search(r"\btop\s+(\d+)\b", text_lower)
        if m:
            limit = int(m.group(1))

        return Intent(
            action=action,
            has_where=has_where,
            has_join=has_join,
            has_group_by=has_group,
            has_order_by=has_order or limit is not None,
            order_dir=order_dir,
            limit=limit,
        )


# ---------------------------------------------------------------------------
# Schema Mapper
# ---------------------------------------------------------------------------

@dataclass
class MappedEntities:
    primary_table: str | None = None
    join_table: str | None = None
    columns: list[str] = field(default_factory=list)
    where_column: str | None = None
    where_op: str = "="
    where_value: Any = None
    group_column: str | None = None
    order_column: str | None = None
    agg_column: str | None = None


class SchemaMapper:
    """Map tokens to schema entities (tables, columns)."""

    OPERATOR_MAP: dict[str, str] = {
        "over": ">", "above": ">", "greater": ">", "more": ">",
        "under": "<", "below": "<", "less": "<", "fewer": "<",
        "equal": "=", "equals": "=", "exactly": "=",
    }

    @classmethod
    def map(cls, tokens: list[str], text: str, schema: Schema, intent: Intent) -> MappedEntities:
        entities = MappedEntities()

        # --- find tables mentioned ---
        tables_found: list[str] = []
        for token in tokens:
            # try singular and plural
            for variant in (token, token + "s", token.rstrip("s")):
                match = schema.find_table(variant)
                if match and match not in tables_found:
                    tables_found.append(match)

        if tables_found:
            entities.primary_table = tables_found[0]
        if len(tables_found) > 1:
            entities.join_table = tables_found[1]
            intent.has_join = True

        # --- find columns ---
        for token in tokens:
            tables_with_col = schema.find_column(token)
            if tables_with_col:
                entities.columns.append(token)

        # --- detect WHERE value (number or quoted string) ---
        num_match = re.search(r"[\$]?([\d]+(?:\.[\d]+)?)", text)
        if num_match and intent.has_where:
            entities.where_value = float(num_match.group(1))
            if entities.where_value == int(entities.where_value):
                entities.where_value = int(entities.where_value)

        # --- detect operator ---
        for token in tokens:
            if token in cls.OPERATOR_MAP:
                entities.where_op = cls.OPERATOR_MAP[token]
                break

        # --- guess where_column: a numeric column near the operator ---
        if entities.where_value is not None and entities.primary_table:
            target_table = entities.join_table or entities.primary_table
            for col in schema.get_columns(target_table):
                if col.lower() in ("total", "amount", "price", "salary", "age", "quantity", "cost"):
                    entities.where_column = col
                    break
            if entities.where_column is None and entities.columns:
                entities.where_column = entities.columns[-1]

        # --- aggregate column ---
        if intent.action in ("average", "sum", "max", "min", "count"):
            if entities.where_column:
                entities.agg_column = entities.where_column
            elif entities.columns:
                entities.agg_column = entities.columns[0]

        # --- group column ---
        if intent.has_group_by and entities.columns:
            entities.group_column = entities.columns[0]

        # --- order column ---
        if intent.has_order_by:
            entities.order_column = entities.agg_column or (entities.columns[0] if entities.columns else None)

        return entities


# ---------------------------------------------------------------------------
# SQL Builder
# ---------------------------------------------------------------------------

class SQLBuilder:
    """Assemble a SQL string from intent + mapped entities."""

    @staticmethod
    def build(intent: Intent, entities: MappedEntities, schema: Schema, config: Config | None = None) -> str:
        if entities.primary_table is None:
            raise ValueError("Could not determine target table from the query.")

        parts: list[str] = []
        table = entities.primary_table

        # --- SELECT clause ---
        agg_col_full = None
        if entities.agg_column:
            tbl = entities.join_table or table
            agg_col_full = f"{tbl}.{entities.agg_column}"

        if intent.action == "count":
            select_expr = f"COUNT(*)"
        elif intent.action == "average" and agg_col_full:
            select_expr = f"AVG({agg_col_full})"
        elif intent.action == "sum" and agg_col_full:
            select_expr = f"SUM({agg_col_full})"
        elif intent.action == "max" and agg_col_full:
            select_expr = f"MAX({agg_col_full})"
        elif intent.action == "min" and agg_col_full:
            select_expr = f"MIN({agg_col_full})"
        else:
            select_expr = f"{table}.*"

        parts.append(f"SELECT {select_expr}")

        # --- FROM ---
        parts.append(f"FROM {table}")

        # --- JOIN ---
        if intent.has_join and entities.join_table:
            jt = entities.join_table
            join_cols = schema.detect_join_column(table, jt)
            if join_cols:
                parts.append(f"JOIN {jt} ON {join_cols[0]} = {join_cols[1]}")
            else:
                parts.append(f"JOIN {jt}")

        # --- WHERE ---
        if intent.has_where and entities.where_column and entities.where_value is not None:
            tbl = entities.join_table or table
            val = entities.where_value
            if isinstance(val, str):
                val = f"'{val}'"
            parts.append(f"WHERE {tbl}.{entities.where_column} {entities.where_op} {val}")

        # --- GROUP BY ---
        if intent.has_group_by and entities.group_column:
            parts.append(f"GROUP BY {table}.{entities.group_column}")

        # --- ORDER BY ---
        if intent.has_order_by and entities.order_column:
            tbl = entities.join_table or table
            parts.append(f"ORDER BY {tbl}.{entities.order_column} {intent.order_dir}")

        # --- LIMIT ---
        if intent.limit:
            parts.append(f"LIMIT {intent.limit}")

        return " ".join(parts)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class Validator:
    """Basic SQL safety and correctness checks."""

    DANGEROUS_KEYWORDS = {"DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE", "EXEC", "EXECUTE"}

    @classmethod
    def validate(cls, sql: str) -> tuple[bool, str]:
        upper = sql.upper().strip()

        if not upper.startswith("SELECT"):
            return False, "Only SELECT queries are supported."

        for kw in cls.DANGEROUS_KEYWORDS:
            if re.search(rf"\b{kw}\b", upper):
                return False, f"Dangerous keyword detected: {kw}"

        # Basic balanced parentheses
        if sql.count("(") != sql.count(")"):
            return False, "Unbalanced parentheses."

        return True, "OK"


# ---------------------------------------------------------------------------
# QueryEngine (main entry point)
# ---------------------------------------------------------------------------

class QueryEngine:
    """High-level API: natural language in, SQL out."""

    def __init__(self, schema: Schema, config: Config | None = None) -> None:
        self.schema = schema
        self.config = config or Config()
        self.tokenizer = Tokenizer()
        self.classifier = IntentClassifier()
        self.mapper = SchemaMapper()
        self.builder = SQLBuilder()
        self.validator = Validator()

    def translate(self, question: str) -> str:
        """Convert a natural-language *question* to a SQL query string."""
        return self.explain(question).sql

    def explain(self, question: str) -> "Explanation":
        """Same as :meth:`translate`, but also returns the intermediate
        decisions (tokens, intent, mapped entities) so callers can show
        *why* the SQL came out the way it did."""
        tokens = self.tokenizer.tokenize(question)
        clean_tokens = self.tokenizer.remove_stop_words(tokens)
        intent = self.classifier.classify(question, clean_tokens)
        entities = self.mapper.map(clean_tokens, question, self.schema, intent)
        sql = self.builder.build(intent, entities, self.schema, self.config)

        if self.config.validate:
            ok, msg = self.validator.validate(sql)
            if not ok:
                raise ValueError(f"Generated SQL failed validation: {msg}")

        return Explanation(
            question=question,
            tokens=tokens,
            clean_tokens=clean_tokens,
            intent=intent,
            entities=entities,
            sql=normalize_whitespace(sql),
        )


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------


@dataclass
class Explanation:
    """Step-by-step trace of the translation pipeline.

    Useful for debugging "why did it pick that table?" or for surfacing
    the engine's reasoning to end users in a UI.
    """

    question: str
    tokens: list[str]
    clean_tokens: list[str]
    intent: Intent
    entities: MappedEntities
    sql: str

    def render(self) -> str:
        """Pretty-print the explanation as a single human-readable string."""
        lines = [
            f"question: {self.question}",
            f"tokens:   {self.tokens}",
            f"keywords: {self.clean_tokens}",
            f"intent:   action={self.intent.action}"
            f"  where={self.intent.has_where}  join={self.intent.has_join}"
            f"  group_by={self.intent.has_group_by}  order_by={self.intent.has_order_by}"
            f"  limit={self.intent.limit}",
            f"primary table: {self.entities.primary_table}",
            f"join table:    {self.entities.join_table}",
            f"columns:       {self.entities.columns}",
            f"where col/op/val: {self.entities.where_column} {self.entities.where_op}"
            f" {self.entities.where_value}",
            f"agg col:       {self.entities.agg_column}",
            f"order col:     {self.entities.order_column}",
            "",
            f"sql: {self.sql}",
        ]
        return "\n".join(lines)
