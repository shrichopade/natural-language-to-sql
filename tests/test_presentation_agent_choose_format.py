"""
tests/test_presentation_agent_choose_format.py — tests for presentation format selection.

These tests avoid calling the LLM and focus on deterministic format inference.
"""

from app.agents.presentation_agent import _choose_format


def test_choose_format_prefers_explicit_user_request() -> None:
    # If the user asks for a bar chart, we should respect that.
    state = {"query": "Please show a bar chart", "preferred_format": "auto", "sql_results": [(1, 2)]}
    assert _choose_format(state) == "bar_chart"


def test_choose_format_infers_line_chart_for_date_and_number() -> None:
    # Date-like x + numeric y should become a line chart.
    state = {"query": "auto", "preferred_format": "auto", "sql_results": [("2026-01-01", 10.0)]}
    assert _choose_format(state) == "line_chart"

