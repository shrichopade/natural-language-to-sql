from __future__ import annotations

# orchestrator.py — runs the agents in order (schema → SQL → execute → critique → presentation).

from typing import Any, Dict, TypedDict

from agents.data_critic_agent import criticize_results
from agents.guardrail_agent import validate_and_execute
from agents.metadata_agent import get_schema
from agents.presentation_agent import format_presentation
from agents.sql_generator_agent import generate_sql


class AgentState(TypedDict, total=False):
    query: str
    preferred_format: str
    schema: Any
    sql_query: str
    sql_results: Any
    analysis: str
    viz_code: str
    error: str


# Run the full pipeline and return the final state.
# Takes an initial state dict, returns the updated state dict.
def app_graph(state: AgentState) -> AgentState:
    """
    Orchestrate the NL->SQL pipeline.

    Runs: schema -> SQL generation -> guardrail/execute -> critic -> presentation
    Retries once if the critic or DB reports an error.
    """
    # Ensure schema is present
    state = get_schema(state)

    original_query = (state.get("query") or "").strip()
    preferred_format = (state.get("preferred_format") or "").strip()

    last_error: str | None = None
    for attempt in range(2):
        if attempt == 0:
            state["query"] = original_query
        else:
            feedback = last_error or state.get("error") or "The previous attempt did not answer the question."
            state["query"] = (
                f"{original_query}\n\n"
                f"Previous attempt feedback (fix this): {feedback}\n"
                "Return a corrected SQLite SELECT query."
            )

        # Keep the preferred_format stable across retries
        if preferred_format:
            state["preferred_format"] = preferred_format

        state.pop("error", None)
        state.pop("analysis", None)
        state.pop("viz_code", None)

        state = generate_sql(state)
        state = validate_and_execute(state)

        # If guardrail / DB error, retry
        if state.get("error"):
            last_error = state.get("error")
            continue

        state = criticize_results(state)
        if state.get("error"):
            last_error = state.get("error")
            continue

        state = format_presentation(state)
        return state

    # Ran out of retries. Return state with last error preserved.
    if last_error:
        state["error"] = last_error
    return state

