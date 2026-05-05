from __future__ import annotations

# main.py — backwards-compatible entry point.
#
# Streamlit renders top-level string literals, so we use comments (not a docstring).
# This file forwards to the real app entry point in `app/main.py`.

from app.main import main


if __name__ == "__main__":
    # Call the new entry point inside the `app/` package.
    main()

