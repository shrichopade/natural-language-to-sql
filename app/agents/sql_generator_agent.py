from __future__ import annotations

# app/agents/sql_generator_agent.py — turns a user question + schema into a SQLite SELECT query.

import re
from typing import Any, Optional, TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import GOOGLE_API_KEY, OLLAMA_MODEL


class AgentState(TypedDict, total=False):
    query: str
    schema: Any
    sql_query: str


_MONTHLY_SALES_LAST_YEAR_RE = re.compile(
    r"\b(total\s+sales)\b.*\bby\s+month\b.*\b(last\s+year|past\s+year|previous\s+year)\b",
    re.IGNORECASE,
)
_REGION_SALES_LAST_6_MONTHS_RE = re.compile(
    r"\b(total\s+sales)\b.*\bby\s+region\b.*\b(last\s+6\s+months|past\s+6\s+months)\b",
    re.IGNORECASE,
)


# Return known-good SQL for a few common questions.
# Takes the user's text, returns SQL (or None if we don't have a safe shortcut).
def _rule_based_sql(user_query: str) -> Optional[str]:
    """
    High-reliability SQL for a couple of common analytics questions.
    """
    q = user_query.strip()

    # Total sales by month for last year
    if _MONTHLY_SALES_LAST_YEAR_RE.search(q):
        return """
SELECT
  strftime('%Y-%m', o.order_date) AS month,
  ROUND(SUM(od.unit_price * od.quantity * (1 - COALESCE(od.discount, 0))), 2) AS total_sales
FROM orders o
JOIN order_details od ON od.order_id = o.order_id
WHERE date(o.order_date) >= date('now', '-1 year')
GROUP BY 1
ORDER BY 1;
""".strip()

    # Total sales by region for last 6 months (region inferred via employee territory -> region)
    if _REGION_SALES_LAST_6_MONTHS_RE.search(q):
        return """
SELECT
  r.region_name AS region,
  ROUND(SUM(od.unit_price * od.quantity * (1 - COALESCE(od.discount, 0))), 2) AS total_sales
FROM orders o
JOIN order_details od ON od.order_id = o.order_id
JOIN employees e ON e.emp_id = o.emp_id
JOIN territories t ON t.territory_id = e.territory_id
JOIN regions r ON r.region_id = t.region_id
WHERE date(o.order_date) >= date('now', '-6 months')
GROUP BY 1
ORDER BY total_sales DESC;
""".strip()

    return None


# Turn the schema object into readable text for the model prompt.
# Takes the schema from state, returns a plain-text description.
def _schema_to_text(schema: Any) -> str:
    """
    Convert schema object (dict/str/etc.) into prompt-friendly text.
    """
    if schema is None:
        return ""
    if isinstance(schema, str):
        return schema
    if isinstance(schema, dict):
        tables = schema.get("tables")
        if isinstance(tables, list):
            parts: list[str] = []
            for t in tables:
                if not isinstance(t, dict):
                    continue
                name = t.get("name")
                create_sql = t.get("create_sql") or t.get("sql")
                if name and create_sql:
                    parts.append(f"-- {name}\n{str(create_sql).strip()}")
            if parts:
                return "\n\n".join(parts)
    return str(schema)


# Clean up the model output so we end up with raw SQL only.
# Takes model text, returns just the SQL string.
def _extract_sql(text: str) -> str:
    """
    Best-effort cleanup to enforce raw SQL only.
    """
    sql = (text or "").strip()
    if "```" in sql:
        # Remove fenced code blocks if the model ignored instructions.
        sql = sql.replace("```sql", "").replace("```SQL", "").replace("```", "").strip()
    return sql


# Generate a SQLite query and store it back into `state["sql_query"]`.
# Takes the agent state, returns the updated state.
def generate_sql(state: AgentState, *, model: str = OLLAMA_MODEL) -> AgentState:
    """
    Generate a SQLite query from state['query'] using state['schema'].

    Stores raw SQL in state['sql_query'] (no markdown, no explanation).
    """
    user_query = (state.get("query") or "").strip()
    schema_text = _schema_to_text(state.get("schema"))

    if not user_query:
        # No question means there's nothing to query.
        state["sql_query"] = ""
        return state

    # Fast-path for common business questions where we can be exact.
    rule_sql = _rule_based_sql(user_query)
    if rule_sql:
        # Use a hard-coded query when we can be exact and reliable.
        state["sql_query"] = rule_sql
        return state

    if not schema_text:
        # Without schema, the model would guess table/column names.
        state["sql_query"] = ""
        return state

    system_prompt = (
        "You are a master SQLite expert.\n"
        "Given a database schema and a user's question, output a single SQLite SQL query.\n"
        "Rules:\n"
        "- Output ONLY the raw SQL query text.\n"
        "- No explanations.\n"
        "- No markdown.\n"
        "- No backticks.\n"
        "- Do not include multiple alternatives.\n"
        "- Use only tables/columns present in the schema.\n"
        "- Prefer explicit JOINs when needed.\n"
        "- If the question asks for a date range like 'last year' or 'last 6 months', use SQLite date functions like date('now','-1 year') and date('now','-6 months').\n"
        "- For month grouping, use strftime('%Y-%m', <date_column>).\n"
    )

    human_prompt = (
        "SCHEMA (SQLite CREATE TABLE statements):\n"
        f"{schema_text}\n\n"
        "USER QUESTION:\n"
        f"{user_query}\n\n"
        "Return ONLY the SQL query."
    )

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY)
        result = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
        state["sql_query"] = _extract_sql(getattr(result, "content", str(result)))
        return state
    except Exception as e:
        state["sql_query"] = ""
        state["sql_error"] = str(e)
        return state

