# Natural Language → SQL (SQLite) — Streamlit + Gemini

Ask questions in plain English and get:

- a generated **SQLite SELECT** query
- query results from a local SQLite database (`sales.db`)
- a short natural-language summary
- a simple chart/table visualization

## What’s inside

- **App UI**: `app/main.py` (Streamlit)
- **Pipeline orchestrator**: `app/orchestrator.py`
- **Pipeline steps (“agents”)**: `app/agents/`
- **Database schema**: `database/schema.sql`
- **Docs**
  - `SOLUTION_DESIGN.md`
  - `ER_DIAGRAM.md` (Mermaid ER diagram)

## Requirements

- Python 3.10+ recommended

Install Python packages:

```bash
pip install -r requirements.txt
```

## Setup (API key)

This project reads your Gemini key from environment variables.

1) Copy the template:

```bash
copy .env.example .env
```

2) Put your key into `.env`:

```env
GOOGLE_API_KEY=your_key_here
```

Notes:
- **Do not commit** `.env` (it is ignored by `.gitignore`).

## Initialize the database

Create the SQLite tables:

```bash
python .\database\setup_db.py
```

Optional: seed the database with fake sample data (uses `faker`):

```bash
python .\database\seed_data.py
```

## Run the app

Start Streamlit:

```bash
streamlit run .\app\main.py
```

Then open the local URL Streamlit prints in your terminal.

Compatibility note:
- You can also run `streamlit run .\main.py` (it forwards to `app/main.py`).

## Example questions to try

- “What were total sales by month in the last year?”
- “Show total sales by region for the last 6 months”
- “Which products have the highest total sales?”
- “Show me total sales by customer country”

## Safety (important)

- Only **SELECT** queries are allowed.
- SQL statements like `DELETE`, `DROP`, `UPDATE`, and `INSERT` are blocked before execution.

## More context

- Solution design: `SOLUTION_DESIGN.md`
- Database ER diagram: `ER_DIAGRAM.md`
- Database/table guide for prompting: `.cursor/rules/PROJECT_CONTEXT.mdc`

