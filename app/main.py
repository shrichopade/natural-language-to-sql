from __future__ import annotations

# app/main.py — Streamlit UI for the Natural Language → SQL app (login, chat, results, charts).

import base64
import hashlib
import hmac
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

import streamlit as st

try:
    import plotly.graph_objects as go
except Exception:  # pragma: no cover
    go = None  # type: ignore

from app.orchestrator import app_graph


APP_DIR = Path(__file__).resolve().parent.parent
USERS_DB_PATH = APP_DIR / "users.db"

_LIGHT_CSS = """
<style>
  /* App background: calm, minimal, readable */
  .stApp {
    background:
      radial-gradient(1200px 700px at 10% 5%, rgba(99, 102, 241, 0.14) 0%, rgba(255, 255, 255, 0) 55%),
      radial-gradient(1200px 700px at 92% 8%, rgba(14, 165, 233, 0.10) 0%, rgba(255, 255, 255, 0) 55%),
      linear-gradient(180deg, #f7f9ff 0%, #ffffff 100%);
  }
  .stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background-image:
      linear-gradient(90deg, rgba(15, 23, 42, 0.05) 1px, rgba(0,0,0,0) 1px),
      linear-gradient(0deg, rgba(15, 23, 42, 0.05) 1px, rgba(0,0,0,0) 1px);
    background-size: 44px 44px, 44px 44px;
    mix-blend-mode: multiply;
    opacity: 0.16;
  }
  /* Content width: keep reading comfortable on wide screens */
  section.main > div.block-container {
    max-width: 1080px;
    padding-top: 2.0rem;
    padding-bottom: 2.0rem;
  }
  .eda-header {
    padding: 0.25rem 0 0.75rem 0;
  }
  .eda-title {
    font-size: 2.0rem;
    font-weight: 760;
    letter-spacing: -0.02em;
    margin: 0;
    color: #0f172a;
  }
  .eda-subtitle {
    margin-top: 0.25rem;
    color: #475569;
    font-size: 0.95rem;
    line-height: 1.5;
  }
  .eda-card {
    background: rgba(255, 255, 255, 0.90);
    border: 1px solid rgba(148, 163, 184, 0.18);
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.07);
    border-radius: 16px;
    padding: 1.05rem 1.05rem;
    max-width: 520px; /* pleasant form width */
    margin: 0 auto;
  }
  .eda-pill {
    display: inline-block;
    padding: 0.25rem 0.6rem;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(99, 102, 241, 0.16), rgba(14, 165, 233, 0.16));
    color: #1d4ed8;
    border: 1px solid rgba(99, 102, 241, 0.22);
    font-size: 0.85rem;
  }
  .eda-muted {
    color: #64748b;
    font-size: 0.9rem;
  }
  h1, h2, h3 {
    color: #0f172a;
  }
  .eda-section {
    background: rgba(255, 255, 255, 0.84);
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 16px;
    padding: 0.95rem 1.0rem;
    box-shadow: 0 10px 22px rgba(15, 23, 42, 0.06);
  }
  div[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(245, 248, 255, 0.98) 0%, rgba(255, 255, 255, 0.98) 100%);
    border-right: 1px solid rgba(148, 163, 184, 0.22);
  }
  div[data-testid="stSidebar"] .stButton button {
    border-radius: 10px;
  }
  .stButton button[kind="primary"] {
    border-radius: 10px;
    box-shadow: 0 8px 18px rgba(37, 99, 235, 0.18);
  }
  /* Reduce visual noise around inputs */
  div[data-baseweb="input"] > div,
  div[data-baseweb="textarea"] > div {
    border-radius: 12px !important;
  }
  div[data-baseweb="select"] > div {
    border-radius: 12px !important;
  }
  div[data-testid="stExpander"] {
    border: 1px solid rgba(148, 163, 184, 0.20);
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.55);
  }
  div[data-testid="stToast"] {
    border-radius: 12px;
  }
</style>
"""


# Apply the CSS theme so the app looks consistent across pages.
# Takes nothing in, returns nothing.
def _apply_style() -> None:
    st.markdown(_LIGHT_CSS, unsafe_allow_html=True)


# Open a connection to the SQLite file at `db_path`.
# Takes a file path, returns a ready-to-use database connection.
def _get_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# Create the user/login tables if they do not exist yet.
# Takes nothing in, returns nothing.
def _init_users_db() -> None:
    with _get_conn(USERS_DB_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user','assistant')),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
            """
        )


# Convert a plain-text password into a safe stored string.
# Takes a password, returns a salted+hashed string you can store in the DB.
def _hash_password(password: str, *, iterations: int = 200_000) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


# Check if a plain-text password matches the saved hash.
# Takes the password + stored hash, returns True/False.
def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters_s, salt_b64, dk_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iters_s)
        salt = base64.b64decode(salt_b64.encode())
        expected = base64.b64decode(dk_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(expected, actual)
    except Exception:
        return False


# Create a new user account.
# Takes username/password, returns (success flag, message).
def _create_user(username: str, password: str) -> tuple[bool, str]:
    if not username or not password:
        return False, "Username and password are required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    try:
        with _get_conn(USERS_DB_PATH) as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username.strip(), _hash_password(password)),
            )
        return True, "Account created. Please log in."
    except sqlite3.IntegrityError:
        return False, "That username is already taken."
    except sqlite3.Error as e:
        return False, str(e)


# Check login credentials against the database.
# Takes username/password, returns (success flag, user_id, message).
def _authenticate(username: str, password: str) -> tuple[bool, Optional[int], str]:
    try:
        with _get_conn(USERS_DB_PATH) as conn:
            row = conn.execute(
                "SELECT user_id, password_hash FROM users WHERE username = ?",
                (username.strip(),),
            ).fetchone()
        if not row:
            return False, None, "Invalid username or password."
        user_id, stored_hash = int(row[0]), str(row[1])
        if not _verify_password(password, stored_hash):
            return False, None, "Invalid username or password."
        return True, user_id, ""
    except sqlite3.Error as e:
        return False, None, str(e)


# Load the latest chat history for the given user.
# Takes user_id (and an optional limit), returns a list of role/content messages.
def _load_history(user_id: int, *, limit: int = 200) -> list[dict[str, str]]:
    try:
        with _get_conn(USERS_DB_PATH) as conn:
            rows = conn.execute(
                """
                SELECT role, content
                FROM chat_messages
                WHERE user_id = ?
                ORDER BY message_id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        # Return in chronological order
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    except sqlite3.Error:
        return []


# Save a single chat message to the database.
# Takes user_id/role/content, returns nothing.
def _append_message(user_id: int, role: str, content: str) -> None:
    try:
        with _get_conn(USERS_DB_PATH) as conn:
            conn.execute(
                "INSERT INTO chat_messages (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content),
            )
    except sqlite3.Error:
        pass


# Run the LLM-generated visualization code, but with very limited access.
# Takes the code string, returns nothing.
def _safe_exec_viz(code: str) -> None:
    """
    Execute visualization code with a very small surface area.

    - Removes any import statements.
    - Provides only `st` and `go` to the snippet.
    """
    if not code.strip():
        return

    # Remove any import lines so the snippet cannot pull in extra modules.
    sanitized_lines: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            continue
        sanitized_lines.append(line)
    sanitized = "\n".join(sanitized_lines).strip()
    if not sanitized:
        return

    # Only allow a small set of Python "built-in" helpers inside the snippet.
    safe_builtins: dict[str, Any] = {
        "dict": dict,
        "list": list,
        "tuple": tuple,
        "set": set,
        "len": len,
        "range": range,
        "min": min,
        "max": max,
        "sum": sum,
        "sorted": sorted,
        "enumerate": enumerate,
        "zip": zip,
        "abs": abs,
        "round": round,
        "int": int,
        "float": float,
        "str": str,
    }

    # The snippet can only see Streamlit (`st`) and optionally Plotly (`go`).
    allowed_globals: dict[str, Any] = {"st": st, "__builtins__": safe_builtins}
    if go is not None:
        allowed_globals["go"] = go
    exec(sanitized, allowed_globals, {})


# Draw a simple chart/table without executing any model-generated code.
# Takes query results + the user's preferred format, returns nothing.
def _fallback_render(sql_results: Any, preferred_format: str) -> None:
    """
    Render a simple visualization without executing LLM code.
    Expects sql_results as list[tuple], where first two columns are x/label and y/value.
    """
    rows = sql_results if isinstance(sql_results, (list, tuple)) else []
    if not rows:
        st.info("No data to display.")
        return

    # Table always works.
    if preferred_format in {"table"}:
        st.dataframe(rows)
        return

    if go is None:
        st.dataframe(rows)
        return

    # Try to infer x/y from the first two columns so we can chart it.
    x = [r[0] for r in rows if isinstance(r, (list, tuple)) and len(r) >= 2]
    y_raw = [r[1] for r in rows if isinstance(r, (list, tuple)) and len(r) >= 2]
    if not x or not y_raw:
        st.dataframe(rows)
        return

    try:
        y = [float(v) if v is not None else 0.0 for v in y_raw]
    except Exception:
        st.dataframe(rows)
        return

    if preferred_format in {"line chart", "line"}:
        fig = go.Figure(data=go.Scatter(x=x, y=y, mode="lines+markers"))
        st.plotly_chart(fig, use_container_width=True)
        return

    if preferred_format in {"bar chart", "bar"}:
        fig = go.Figure(data=go.Bar(x=x, y=y))
        st.plotly_chart(fig, use_container_width=True)
        return

    if preferred_format in {"pie chart", "pie"}:
        fig = go.Figure(data=go.Pie(labels=x, values=y))
        st.plotly_chart(fig, use_container_width=True)
        return

    # Auto / unknown
    fig = go.Figure(data=go.Bar(x=x, y=y))
    st.plotly_chart(fig, use_container_width=True)


# Show the login/sign-up screen and handle auth actions.
# Takes nothing in, returns nothing.
def _login_ui() -> None:
    _apply_style()
    _l, _c, _r = st.columns([0.12, 0.76, 0.12])
    with _c:
        st.markdown(
            """
            <div class="eda-header">
              <div class="eda-pill">Enterprise Data Assistant</div>
              <h1 class="eda-title">Welcome back</h1>
              <div class="eda-subtitle">Sign in to ask questions, validate SQL, and tell the story in charts.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

        with tab_login:
            _c2, _c3, _c4 = st.columns([0.18, 0.64, 0.18])
            with _c3:
                st.markdown("<div class='eda-card'>", unsafe_allow_html=True)
                with st.form("login_form", clear_on_submit=False):
                    username = st.text_input("Username", key="login_username", placeholder="e.g., shric")
                    password = st.text_input("Password", type="password", key="login_password")
                    submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            if submitted:
                ok, user_id, msg = _authenticate(username, password)
                if ok and user_id is not None:
                    # Remember the logged-in user so we can show the app UI.
                    st.session_state["authenticated"] = True
                    st.session_state["user_id"] = user_id
                    st.session_state["username"] = username.strip()
                    st.session_state["messages"] = _load_history(user_id)
                    st.rerun()
                else:
                    st.error(msg or "Login failed.")

        with tab_signup:
            _c2, _c3, _c4 = st.columns([0.18, 0.64, 0.18])
            with _c3:
                st.markdown("<div class='eda-card'>", unsafe_allow_html=True)
                with st.form("signup_form", clear_on_submit=True):
                    username = st.text_input("Choose a username", key="signup_username")
                    password = st.text_input(
                        "Choose a password",
                        type="password",
                        key="signup_password",
                        help="Minimum 6 characters.",
                    )
                    submitted = st.form_submit_button("Create account", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            if submitted:
                ok, msg = _create_user(username, password)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)


# Show the main app screen (query input, history, results, chart).
# Takes nothing in, returns nothing.
def _app_ui() -> None:
    _apply_style()
    st.sidebar.title("Enterprise Data Assistant")
    st.sidebar.caption(f"Signed in as **{st.session_state.get('username','')}**")

    col_a, col_b = st.sidebar.columns(2)
    with col_a:
        if st.button("New Chat", use_container_width=True):
            # Clear the on-screen history; the DB history is still kept.
            st.session_state["messages"] = []
            st.rerun()
    with col_b:
        if st.button("Log out", use_container_width=True):
            # Remove auth/session keys so the user returns to the login page.
            for k in ["authenticated", "user_id", "username", "messages"]:
                st.session_state.pop(k, None)
            st.rerun()

    with st.sidebar.expander("History", expanded=True):
        msgs = st.session_state.get("messages", [])
        if not msgs:
            st.caption("No messages yet.")
        else:
            user_queries = [m.get("content", "") for m in msgs if m.get("role") == "user"]
            page_size = 10
            total = len(user_queries)
            if total == 0:
                st.caption("No queries yet.")
            else:
                total_pages = max(1, (total + page_size - 1) // page_size)
                if "history_page" not in st.session_state:
                    # Start on the newest page of messages by default.
                    st.session_state["history_page"] = total_pages - 1  # default to newest

                # Clamp in case the user added new messages
                st.session_state["history_page"] = max(0, min(st.session_state["history_page"], total_pages - 1))
                page = int(st.session_state["history_page"])

                start = page * page_size
                end = min(start + page_size, total)
                page_items = user_queries[start:end]

                nav_l, nav_r = st.columns(2)
                with nav_l:
                    prev_disabled = page <= 0
                    if st.button("◀ Prev", use_container_width=True, disabled=prev_disabled):
                        st.session_state["history_page"] = max(0, page - 1)
                        st.rerun()
                with nav_r:
                    next_disabled = page >= total_pages - 1
                    if st.button("Next ▶", use_container_width=True, disabled=next_disabled):
                        st.session_state["history_page"] = min(total_pages - 1, page + 1)
                        st.rerun()

                st.caption(f"Showing {start + 1}-{end} of {total}")
                for i, q in enumerate(page_items, start=start + 1):
                    st.markdown(f"**{i}.** {q}")

    st.markdown(
        """
        <div class="eda-header">
          <div class="eda-pill">Ask • Analyze • Visualize</div>
          <h1 class="eda-title">Ask your data a question</h1>
          <div class="eda-subtitle">Natural language → SQL → results with a concise summary and visualization.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    format_map = {
        "Auto": "auto",
        "Table": "table",
        "Bar Chart": "bar chart",
        "Line Chart": "line chart",
        "Pie Chart": "pie chart",
    }

    st.markdown("<div class='eda-section'>", unsafe_allow_html=True)
    top_left, top_right = st.columns([3, 1])
    with top_left:
        query = st.text_input(
            "Ask your data a question",
            key="nl_query",
            placeholder="e.g., What were total sales by month in the last year?",
        )
    with top_right:
        preferred = st.selectbox("Preferred Format", list(format_map.keys()), index=0)
    st.markdown("</div>", unsafe_allow_html=True)

    run = st.button("Run", type="primary", use_container_width=False)

    if run:
        user_id = int(st.session_state["user_id"])
        if not query.strip():
            st.warning("Please enter a question.")
            return

        # Save the user's message to history before we run the pipeline.
        _append_message(user_id, "user", query.strip())
        st.session_state["messages"] = (st.session_state.get("messages") or []) + [
            {"role": "user", "content": query.strip()}
        ]

        with st.spinner("Thinking…"):
            state: dict[str, Any] = {
                "query": query.strip(),
                "preferred_format": format_map[preferred],
            }
            state = app_graph(state)  # type: ignore[arg-type]

        if state.get("error"):
            st.error(state["error"])
            return

        analysis = (state.get("analysis") or "").strip()
        if analysis:
            st.markdown("<div class='eda-section'>", unsafe_allow_html=True)
            st.subheader("Natural Language Summary")
            st.write(analysis)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='eda-section'>", unsafe_allow_html=True)
        st.subheader("Visualization")
        # Store results in session state so the chart code can access them.
        st.session_state["sql_results"] = state.get("sql_results", [])
        viz_code = (state.get("viz_code") or "").strip()
        if viz_code:
            try:
                _safe_exec_viz(viz_code)
            except Exception as e:
                st.error(f"Failed to render visualization: {e}")
                # Fallback renderer based on the user's chosen format
                _fallback_render(st.session_state.get("sql_results", []), format_map[preferred])
                st.caption("Showing fallback chart; generated code shown below for debugging.")
                st.code(viz_code)
        else:
            st.info("No visualization code was generated.")
        st.markdown("</div>", unsafe_allow_html=True)

        assistant_msg = analysis or "Done."
        _append_message(user_id, "assistant", assistant_msg)
        st.session_state["messages"] = (st.session_state.get("messages") or []) + [
            {"role": "assistant", "content": assistant_msg}
        ]


# Streamlit entry point: sets up the page and chooses login vs app UI.
# Takes nothing in, returns nothing.
def main() -> None:
    st.set_page_config(page_title="Enterprise Data Assistant", layout="wide")
    _init_users_db()

    if not st.session_state.get("authenticated"):
        _login_ui()
        return
    _app_ui()


if __name__ == "__main__":
    main()

