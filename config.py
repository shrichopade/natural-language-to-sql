from __future__ import annotations

# config.py — central place for app configuration (DB paths + API keys).

import os
from pathlib import Path

# Load `.env` early so modules that import config
# can immediately see GOOGLE_API_KEY via os.environ.
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None  # type: ignore

if load_dotenv is not None:
    # This copies variables from `.env` into `os.environ` for local development.
    load_dotenv()

# Project root directory (this file lives at repo root).
PROJECT_ROOT = Path(__file__).resolve().parent

# --- Database (sales) ---
SALES_DB_PATH = PROJECT_ROOT / "sales.db"
DATABASE_URL = f"sqlite:///{SALES_DB_PATH.as_posix()}"

# --- Ollama / Local LLM ---
OLLAMA_MODEL = "llama3"
OLLAMA_BASE_URL = "http://localhost:11434"

# --- Google Gemini ---
# `langchain_google_genai` reads `GOOGLE_API_KEY` from the environment, but we
# also expose it here so the rest of the app has a single source of truth.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""

