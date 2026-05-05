from __future__ import annotations

"""
orchestrator.py — backwards-compatible import path.

The orchestrator was moved to `app/orchestrator.py`. This file exists so older
imports like `from orchestrator import app_graph` keep working.
"""

from app.orchestrator import app_graph  # noqa: F401

