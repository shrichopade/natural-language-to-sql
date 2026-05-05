from __future__ import annotations

# metadata_agent.py — reads the SQLite database and returns its table schema.

import sqlite3
from typing import Any, Dict, List, TypedDict

from config import SALES_DB_PATH


class AgentState(TypedDict, total=False):
    schema: Any


# Read the database schema and store it in `state["schema"]`.
# Takes agent state, returns updated state.
def get_schema(state: AgentState) -> AgentState:
    """
    Populate state['schema'] with the SQLite database schema.

    Reads from sales.db and extracts all user table names along with their full
    CREATE TABLE statements from sqlite_master.
    """

    db_path = SALES_DB_PATH

    if not db_path.exists():
        state["schema"] = {
            "error": f"Database file not found: {db_path}",
            "tables": [],
        }
        return state

    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT name, sql
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name;
                """
            ).fetchall()

        tables: List[Dict[str, str]] = []
        for r in rows:
            tables.append(
                {
                    "name": str(r["name"]),
                    "create_sql": (r["sql"] or "").strip(),
                }
            )

        state["schema"] = {
            "db_path": str(db_path),
            "tables": tables,
        }
        return state
    except sqlite3.Error as e:
        state["schema"] = {
            "error": f"SQLite error while reading schema: {e}",
            "db_path": str(db_path),
            "tables": [],
        }
        return state
