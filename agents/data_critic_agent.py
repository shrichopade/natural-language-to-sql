from __future__ import annotations

# data_critic_agent.py — checks whether SQL results actually answer the user's question.

import json
from typing import Any, List, Sequence, TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from config import GOOGLE_API_KEY, OLLAMA_MODEL


class AgentState(TypedDict, total=False):
    query: str
    schema: Any
    sql_query: str
    sql_results: Any
    error: str
    analysis: str


# Make a small preview of the results so we do not send huge data to the model.
# Takes the raw results, returns a short JSON string.
def _results_preview(results: Any, *, max_rows: int = 20, max_cell_chars: int = 200) -> str:
    """
    Make a compact, JSON-serializable preview for LLM inspection.
    """
    if results is None:
        return "null"

    if isinstance(results, (str, bytes)):
        s = results.decode("utf-8", errors="replace") if isinstance(results, bytes) else results
        return json.dumps(s[:2000])

    if isinstance(results, dict):
        return json.dumps(results, ensure_ascii=False)[:4000]

    if isinstance(results, (list, tuple)):
        rows = list(results)[:max_rows]
        cooked: list[Any] = []
        for r in rows:
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

    return json.dumps(str(results)[:2000], ensure_ascii=False)


# Decide if the results look correct, and write either an error or a short summary.
# Takes the agent state, returns the updated state.
def criticize_results(state: AgentState, *, model: str = OLLAMA_MODEL) -> AgentState:
    """
    Critic agent: verify results answer the user's question.

    - If empty/wrong: set state['error'] with what's wrong (to trigger retry).
    - If good: set state['analysis'] with a brief natural-language summary.
    """
    user_query = (state.get("query") or "").strip()
    sql_query = (state.get("sql_query") or "").strip()
    results = state.get("sql_results")

    # Basic heuristic: empty results should trigger retry.
    if results is None or results == [] or results == ():
        # Empty results usually means the query was too strict or joined wrong.
        state["error"] = "No results returned; the query may be too restrictive or incorrect for the question."
        state["analysis"] = ""
        return state

    preview = _results_preview(results)

    system_prompt = (
        "You are a careful data critic for a SQLite question-answering system.\n"
        "Your job is to judge whether the SQL results actually answer the user's question.\n"
        "Output format MUST be exactly one of:\n"
        "ERROR: <short description of what's wrong and what to fix>\n"
        "SUMMARY: <brief natural language summary of what the results show>\n"
        "Rules:\n"
        "- Be strict: if results are unrelated, missing key fields, wrong granularity, or likely mis-joined, return ERROR.\n"
        "- If results look correct and sufficient, return SUMMARY.\n"
        "- Do NOT output markdown or backticks.\n"
        "- Keep it concise.\n"
    )

    human_prompt = (
        f"USER QUESTION:\n{user_query}\n\n"
        f"GENERATED SQL:\n{sql_query}\n\n"
        f"SQL RESULTS (preview):\n{preview}\n"
    )

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY)
        msg = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
        text = (getattr(msg, "content", "") or str(msg)).strip()

        if text.upper().startswith("ERROR:"):
            state["error"] = text[len("ERROR:") :].strip() or "Results do not appear to answer the question."
            state["analysis"] = ""
            return state

        if text.upper().startswith("SUMMARY:"):
            state["analysis"] = text[len("SUMMARY:") :].strip()
            state.pop("error", None)
            return state

        # Fallback if the model didn't follow the required prefix
        state["analysis"] = text
        state.pop("error", None)
        return state
    except Exception as e:
        state["error"] = str(e)
        state["analysis"] = ""
        return state

