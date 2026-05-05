from __future__ import annotations

# app/agents/presentation_agent.py — chooses a chart/table and generates Streamlit+Plotly code to render it.

import json
import re
from datetime import datetime
from typing import Any, TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import GOOGLE_API_KEY, OLLAMA_MODEL


class AgentState(TypedDict, total=False):
    query: str
    preferred_format: str
    sql_results: Any
    viz_code: str
    error: str


_EXPLICIT_FORMATS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bline\s*chart\b|\bline\s*graph\b", re.IGNORECASE), "line_chart"),
    (re.compile(r"\bbar\s*chart\b|\bbar\s*graph\b", re.IGNORECASE), "bar_chart"),
    (re.compile(r"\bpie\s*chart\b|\bpie\s*graph\b", re.IGNORECASE), "pie_chart"),
    (re.compile(r"\btable\b|\btabular\b", re.IGNORECASE), "table"),
]


# Check whether a value looks like a date/time so we can pick a good chart type.
# Takes any value, returns True/False.
def _is_date_like(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (datetime,)):
        return True
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s:
        return False
    # Common SQLite-ish date/time formats
    formats: list[tuple[str, int]] = [
        ("%Y-%m-%d", 10),
        ("%Y/%m/%d", 10),
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%dT%H:%M:%S", 19),
    ]
    for fmt, width in formats:
        try:
            # Try the full string first (best case).
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            # If the value includes extra precision (like milliseconds), try a prefix.
            try:
                datetime.strptime(s[:width], fmt)
                return True
            except ValueError:
                continue
    return False


# Check whether a value looks like a number (so it can be plotted on a chart).
# Takes any value, returns True/False.
def _is_number(value: Any) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if isinstance(value, str):
        try:
            float(value.strip())
            return True
        except ValueError:
            return False
    return False


# Create a compact JSON preview of the results for the model prompt.
# Takes rows, returns a short JSON string.
def _rows_preview(rows: Any, *, max_rows: int = 25, max_cell_chars: int = 160) -> str:
    if rows is None:
        return "null"
    if isinstance(rows, (str, bytes)):
        s = rows.decode("utf-8", errors="replace") if isinstance(rows, bytes) else rows
        return json.dumps(s[:2000])
    if isinstance(rows, dict):
        return json.dumps(rows, ensure_ascii=False)[:4000]
    if isinstance(rows, (list, tuple)):
        cooked: list[Any] = []
        for r in list(rows)[:max_rows]:
            if isinstance(r, (list, tuple)):
                cooked.append(
                    [
                        (str(c)[:max_cell_chars] if c is not None else None)
                        for c in list(r)[:50]
                    ]
                )
            else:
                cooked.append(str(r)[:max_cell_chars])
        return json.dumps(cooked, ensure_ascii=False)
    return json.dumps(str(rows)[:2000], ensure_ascii=False)


# Pick the best output format (table / bar / line / pie) based on user hints and data shape.
# Takes agent state, returns a string like "bar_chart".
def _choose_format(state: AgentState) -> str:
    preferred = (state.get("preferred_format") or "").strip().lower()
    if preferred and preferred not in {"auto", "automatic"}:
        mapping = {
            "table": "table",
            "bar chart": "bar_chart",
            "bar": "bar_chart",
            "line chart": "line_chart",
            "line": "line_chart",
            "pie chart": "pie_chart",
            "pie": "pie_chart",
        }
        if preferred in mapping:
            return mapping[preferred]

    q = (state.get("query") or "").strip()
    for pat, fmt in _EXPLICIT_FORMATS:
        if pat.search(q):
            return fmt

    rows = state.get("sql_results")
    if not isinstance(rows, (list, tuple)) or len(rows) == 0:
        return "table"

    first = rows[0]
    if isinstance(first, (list, tuple)):
        ncols = len(first)
        if ncols >= 2:
            x0 = first[0]
            y0 = first[1]
            if _is_date_like(x0) and _is_number(y0):
                return "line_chart"
            if (not _is_date_like(x0)) and _is_number(y0):
                return "bar_chart"
        return "table"

    # Single-column list
    return "table"


# Provide a safe built-in chart snippet if the model fails or returns bad code.
# Takes a chart type, returns a Python code snippet string.
def _template_code(chart_type: str) -> str:
    # Uses only streamlit + plotly (no pandas dependency).
    if chart_type == "line_chart":
        return (
            "rows = st.session_state.get('sql_results', [])\n"
            "if not rows:\n"
            "    st.info('No data to display.')\n"
            "else:\n"
            "    x = [r[0] for r in rows]\n"
            "    y = [r[1] for r in rows]\n"
            "    fig = go.Figure(data=go.Scatter(x=x, y=y, mode='lines+markers'))\n"
            "    fig.update_layout(xaxis_title='x', yaxis_title='y')\n"
            "    st.plotly_chart(fig, use_container_width=True)\n"
        )
    if chart_type == "bar_chart":
        return (
            "rows = st.session_state.get('sql_results', [])\n"
            "if not rows:\n"
            "    st.info('No data to display.')\n"
            "else:\n"
            "    x = [r[0] for r in rows]\n"
            "    y = [r[1] for r in rows]\n"
            "    fig = go.Figure(data=go.Bar(x=x, y=y))\n"
            "    fig.update_layout(xaxis_title='category', yaxis_title='value')\n"
            "    st.plotly_chart(fig, use_container_width=True)\n"
        )
    if chart_type == "pie_chart":
        return (
            "rows = st.session_state.get('sql_results', [])\n"
            "if not rows:\n"
            "    st.info('No data to display.')\n"
            "else:\n"
            "    labels = [r[0] for r in rows]\n"
            "    values = [r[1] for r in rows]\n"
            "    fig = go.Figure(data=go.Pie(labels=labels, values=values))\n"
            "    st.plotly_chart(fig, use_container_width=True)\n"
        )
    # table
    return (
        "rows = st.session_state.get('sql_results', [])\n"
        "if not rows:\n"
        "    st.info('No data to display.')\n"
        "else:\n"
        "    st.dataframe(rows)\n"
    )


# Decide the best visualization format and generate code to display it.
# Takes agent state, returns updated state with `viz_code` filled in.
def format_presentation(state: AgentState, *, model: str = OLLAMA_MODEL) -> AgentState:
    """
    Decide on a visualization format and generate Streamlit/Plotly code to render it.

    Saves snippet in state['viz_code'].
    """
    chart_type = _choose_format(state)
    user_query = (state.get("query") or "").strip()
    results_preview = _rows_preview(state.get("sql_results"))

    system_prompt = (
        "You generate Streamlit + Plotly visualization code for SQL query results.\n"
        "Output ONLY a Python code snippet (no markdown, no backticks, no explanation).\n"
        "Constraints:\n"
        "- Use only: streamlit, plotly.\n"
        "- Do NOT require pandas.\n"
        "- Do NOT include import statements.\n"
        "- Assume `st` and `plotly.graph_objects as go` are already available.\n"
        "- Assume the SQL rows are available as: st.session_state['sql_results'] (list of tuples).\n"
        "- Handle empty results gracefully.\n"
        "- Use Plotly (go.Figure / go.Scatter / go.Bar / go.Pie) and render with st.plotly_chart.\n"
        "- Do NOT use st.line_chart, st.bar_chart, or st.area_chart.\n"
        f"- The selected visualization type is: {chart_type}\n"
        "Guidance by type:\n"
        "- line_chart: first column is x (date/time-like), second is y (numeric)\n"
        "- bar_chart: first column is category label, second is numeric value\n"
        "- pie_chart: first column is label, second is numeric value\n"
        "- table: render rows in a dataframe-like view\n"
    )

    human_prompt = (
        f"USER REQUEST (may include preferred format):\n{user_query}\n\n"
        f"SQL RESULTS PREVIEW (JSON):\n{results_preview}\n\n"
        "Generate the code now."
    )

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY)
        msg = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
        code = (getattr(msg, "content", "") or str(msg)).strip()
        if not code:
            state["viz_code"] = _template_code(chart_type)
            return state
        # Strip fences if the model ignored instructions.
        if "```" in code:
            code = code.replace("```python", "").replace("```", "").strip()
        # If the model used Streamlit chart helpers, replace with safe Plotly template.
        lowered = code.lower()
        if "st.line_chart" in lowered or "st.bar_chart" in lowered or "st.area_chart" in lowered:
            state["viz_code"] = _template_code(chart_type)
            return state
        state["viz_code"] = code
        return state
    except Exception as e:
        state["viz_code"] = _template_code(chart_type)
        state["error"] = str(e)
        return state

