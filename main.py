from __future__ import annotations

"""
main.py — backwards-compatible entry point.

The project code was refactored into the `app/` package. This file exists so
older commands like `streamlit run main.py` still work.
"""

from app.main import main


if __name__ == "__main__":
    # Call the new entry point inside the `app/` package.
    main()

