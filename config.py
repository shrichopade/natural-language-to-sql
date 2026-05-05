from __future__ import annotations

"""
config.py — backwards-compatible import path.

The configuration was moved to `app/config.py`. This file exists so older
imports like `from config import SALES_DB_PATH` keep working.
"""

from app.config import (  # noqa: F401
    DATABASE_URL,
    GOOGLE_API_KEY,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    PROJECT_ROOT,
    SALES_DB_PATH,
)

