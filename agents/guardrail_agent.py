from __future__ import annotations

# guardrail_agent.py — safety check: blocks dangerous SQL and runs safe SELECT queries.

import re
import sqlite3
from typing import Any, List, Optional, TypedDict

from config import SALES_DB_PATH


class AgentState(TypedDict, total=False):
    sql_query: str
    sql_results: Any
    error: str


_FORBIDDEN_KEYWORDS = ("DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE")
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)


# Block unsafe SQL and execute safe queries against the sales database.
# Takes agent state, returns updated state with either results or an error.
def validate_and_execute(state: AgentState) -> AgentState:
    """
    Security layer: blocks mutating SQL and executes safe queries.
    """
    sql = (state.get("sql_query") or "").strip()
    if not sql:
        # Empty query means we return an empty result set.
        state["sql_results"] = []
        return state

    if _FORBIDDEN_RE.search(sql):
        # This prevents write operations like DELETE/DROP from ever running.
        state["error"] = "Security Violation: Unauthorized Action"
        return state

    db_path = SALES_DB_PATH
    if not db_path.exists():
        state["error"] = f"Database file not found: {db_path}"
        state["sql_results"] = []
        return state

    try:
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.cursor()
            cur.execute(sql)
            rows = cur.fetchall()
            # Store as list of rows (tuples) for portability across layers.
            state["sql_results"] = rows
        return state
    except sqlite3.Error as e:
        state["error"] = str(e)
        state["sql_results"] = []
        return state
