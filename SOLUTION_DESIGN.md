# Solution Design — Natural Language → SQL

This document describes the solution design for a simple, safe pipeline that turns a user question into a SQLite **SELECT** query, runs it, and presents results as a short summary plus a chart/table.

## Goals and non-goals

### Goals

- Let non-technical users ask data questions in plain English.
- Generate a single SQLite **SELECT** query using the real schema.
- Block unsafe SQL (writes / schema changes) before execution.
- Provide a quick summary and a simple visualization.

### Non-goals (for now)

- Not a general database admin tool (no `INSERT`/`UPDATE`/`DELETE`).
- Not a multi-database system (only one SQLite file).
- Not a full BI dashboard builder (visuals are lightweight).
- Not long-term analytics storage (results are computed on demand).

## High-level architecture

The UI calls a single orchestrator function. The orchestrator runs small “agent” functions in order, passing a shared dictionary called `state`.

### Components and responsibilities

- **UI (Streamlit)**: login, question input, and results rendering  
  - Main file: `app/main.py`
- **Orchestrator**: runs pipeline steps and handles retry logic  
  - Main file: `app/orchestrator.py`
- **Agents**: small steps that each read and write fields on the shared state dict  
  - Main folder: `app/agents/`
- **Database**: local SQLite file plus schema definitions  
  - Files: `sales.db`, `database/schema.sql`
- **Configuration**: loads environment variables and config constants  
  - File: `app/config.py`

Note: the repo also includes root-level `main.py`, `orchestrator.py`, and `config.py` as small compatibility wrappers so older commands/imports still work.

## End-to-end data flow

Each step takes the current `state` dictionary and returns the updated `state`.

1. **User submits**
   - **Input**: natural language question + preferred format
   - **Writes**: `state["query"]`, `state["preferred_format"]`
   - **Why**: captures user intent and desired output style

2. **Schema load**
   - **Input**: database file path
   - **Writes**: `state["schema"]`
   - **Why**: gives the model the real tables/columns to avoid guessing

3. **SQL generation**
   - **Input**: question + schema
   - **Writes**: `state["sql_query"]`
   - **Why**: creates one SQLite SELECT query

4. **Guardrail + execute**
   - **Input**: generated SQL
   - **Writes**: `state["sql_results"]` (or `state["error"]`)
   - **Why**: blocks unsafe SQL and executes safe SQL against SQLite

5. **Critic**
   - **Input**: question + SQL + results
   - **Writes**: `state["analysis"]` (or `state["error"]`)
   - **Why**: checks whether results actually answer the question

6. **Presentation**
   - **Input**: results + preferred format
   - **Writes**: `state["viz_code"]`
   - **Why**: generates Streamlit+Plotly code for a chart/table

### Retry behavior

If the guardrail step or critic step sets an error, the orchestrator retries once by appending “feedback” to the user question and asking for a corrected SELECT query.

## Database model (what questions are easy)

The database is a typical sales schema with:

- **Order header table**: `orders`
- **Order line items table**: `order_details`

Most “sales” calculations start from those two tables.

### Common join paths

- **Sales by time**: `orders` → `order_details` (group by `orders.order_date`)
- **Sales by product/category**: `order_details` → `products` → `categories`
- **Sales by customer/country**: `orders` → `customers` (+ `order_details` for totals)
- **Sales by region**: `orders` → `employees` → `territories` → `regions` (+ `order_details` for totals)

For a complete table/relationship guide, see `.cursor/rules/PROJECT_CONTEXT.mdc` and `ER_DIAGRAM.md`.

## Safety and security design

### SQL guardrails (runtime)

- Mutating keywords are blocked (e.g. `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`).
- Queries run only against the local `sales.db` SQLite file.
- Results are returned as plain Python tuples (portable between steps).

### Visualization code guardrails (runtime)

- Import lines are removed from model-generated code.
- The snippet runs with a small set of allowed Python built-ins only.
- The snippet only receives Streamlit (`st`) and Plotly (`go`) globals.

### Important risk to keep in mind

Executing generated code is always a risk. The app reduces risk by stripping imports and restricting globals, but the safest long-term approach is to replace generated visualization code with a fixed “chart builder” that never calls `exec()`.

## Configuration and secrets

- API keys must come from **environment variables**.
- Do not commit `.env`.
- Keep `.env.example` as a safe template.

Example:

```env
GOOGLE_API_KEY=...   # local only (do not commit)
```

Model used by the agents:

- `gemini-2.5-flash`

Note: the project loads `.env` early in `app/config.py` so agent modules can access the key when they are imported.

## Operational concerns

- **Latency**
  - Current: one model call per step (SQL generator, critic, presentation)
  - Later: cache repeated questions and schema
- **Cost**
  - Current: no budgeting yet
  - Later: add rate limits and a per-user budget
- **Observability**
  - Current: minimal logging
  - Later: add structured logs and request IDs
- **Reliability**
  - Current: one retry on error
  - Later: more targeted retries and clearer error messages

## Next improvements (practical roadmap)

### UX

- Show the generated SQL (collapsed by default).
- Add a “copy SQL” button.
- Save preferred format per user.

### Accuracy

- Add more rule-based SQL templates for common questions.
- Enforce a strict allow-list of tables/columns from schema.
- Add tests for SQL generation prompts.

### Security

- Remove `exec()` by using a fixed chart renderer.
- Add query timeouts and row limits for safety.
- Add audit logging for executed SQL.

