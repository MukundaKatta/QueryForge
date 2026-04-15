"""Tests for QueryForge core engine."""

import pytest

from queryforge import QueryEngine, Schema, Tokenizer, Validator


@pytest.fixture
def schema() -> Schema:
    return Schema.from_dict(
        {
            "users": ["id", "name", "email", "created_at"],
            "orders": ["id", "user_id", "total", "status"],
            "products": ["id", "name", "price", "category"],
        }
    )


@pytest.fixture
def engine(schema: Schema) -> QueryEngine:
    return QueryEngine(schema)


# ------------------------------------------------------------------
# Tokenizer
# ------------------------------------------------------------------

class TestTokenizer:
    def test_tokenize_removes_punctuation(self):
        tokens = Tokenizer.tokenize("Hello, world! How are you?")
        assert tokens == ["hello", "world", "how", "are", "you"]

    def test_remove_stop_words(self):
        tokens = ["show", "me", "all", "the", "users"]
        cleaned = Tokenizer.remove_stop_words(tokens)
        assert "me" not in cleaned
        assert "the" not in cleaned
        assert "users" in cleaned


# ------------------------------------------------------------------
# Simple SELECT
# ------------------------------------------------------------------

class TestSimpleSelect:
    def test_select_all_users(self, engine: QueryEngine):
        sql = engine.translate("show all users")
        assert "SELECT" in sql
        assert "users" in sql

    def test_select_with_where(self, engine: QueryEngine):
        sql = engine.translate("show me all users who placed orders over $100")
        assert "SELECT" in sql
        assert "> 100" in sql
        assert "JOIN" in sql

    def test_count_query(self, engine: QueryEngine):
        sql = engine.translate("how many orders are there")
        assert "COUNT(*)" in sql
        assert "orders" in sql


# ------------------------------------------------------------------
# Validator
# ------------------------------------------------------------------

class TestValidator:
    def test_valid_select(self):
        ok, msg = Validator.validate("SELECT * FROM users")
        assert ok is True

    def test_rejects_drop(self):
        ok, msg = Validator.validate("SELECT * FROM users; DROP TABLE users")
        assert ok is False
        assert "DROP" in msg

    def test_rejects_non_select(self):
        ok, msg = Validator.validate("DELETE FROM users")
        assert ok is False


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------

class TestSchema:
    def test_find_table(self, schema: Schema):
        assert schema.find_table("users") == "users"
        assert schema.find_table("USERS") == "users"
        assert schema.find_table("nonexistent") is None

    def test_detect_join_column(self, schema: Schema):
        result = schema.detect_join_column("orders", "users")
        assert result is not None
        assert "user_id" in result[0] or "user_id" in result[1]


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------


def test_explain_returns_pipeline_trace() -> None:
    from queryforge import QueryEngine, Schema

    schema = Schema.from_dict({"customers": ["id", "name", "age"]})
    engine = QueryEngine(schema)
    e = engine.explain("how many customers over 30")

    assert e.question == "how many customers over 30"
    assert "customers" in e.tokens
    assert "customers" in e.clean_tokens
    assert e.intent.action == "count"
    assert e.intent.has_where
    assert e.entities.primary_table == "customers"
    assert "COUNT" in e.sql.upper()


def test_explanation_render_includes_key_fields() -> None:
    from queryforge import QueryEngine, Schema

    engine = QueryEngine(Schema.from_dict({"orders": ["id", "total"]}))
    rendered = engine.explain("top 5 orders").render()
    assert "intent:" in rendered
    assert "primary table:" in rendered
    assert "sql:" in rendered
