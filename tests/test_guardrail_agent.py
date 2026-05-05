"""
tests/test_guardrail_agent.py — tests for SQL safety checks.

These tests avoid calling the LLM and focus on deterministic logic.
"""

from app.agents.guardrail_agent import validate_and_execute


def test_guardrail_blocks_delete() -> None:
    # If the SQL contains a dangerous keyword, we should stop before execution.
    state = {"sql_query": "DELETE FROM orders;"}
    out = validate_and_execute(state)
    assert out.get("error") == "Security Violation: Unauthorized Action"

