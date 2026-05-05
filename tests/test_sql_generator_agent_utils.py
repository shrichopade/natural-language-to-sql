"""
tests/test_sql_generator_agent_utils.py — tests for SQL generator helper functions.

These tests avoid calling the LLM and focus on deterministic string cleanup and schema formatting.
"""

from app.agents.sql_generator_agent import _extract_sql, _schema_to_text


def test_extract_sql_strips_code_fences() -> None:
    # The model sometimes returns fenced code; we want raw SQL only.
    raw = "```sql\nSELECT 1;\n```"
    assert _extract_sql(raw) == "SELECT 1;"


def test_schema_to_text_formats_table_blocks() -> None:
    # Convert a schema dict into a readable text prompt for the model.
    schema = {
        "tables": [
            {"name": "orders", "create_sql": "CREATE TABLE orders (order_id INTEGER);"},
            {"name": "order_details", "create_sql": "CREATE TABLE order_details (order_id INTEGER);"},
        ]
    }
    text = _schema_to_text(schema)
    assert "-- orders" in text
    assert "CREATE TABLE orders" in text

