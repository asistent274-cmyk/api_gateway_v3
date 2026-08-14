import sqlite3
import secrets
from contextlib import contextmanager

DB_PATH = "gateway.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                email TEXT PRIMARY KEY,
                requests_used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL REFERENCES accounts(email),
                name TEXT NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


# --- Accounts ---
def get_account(email: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_or_create_account(email: str) -> dict:
    acc = get_account(email)
    if acc:
        return acc
    with get_conn() as conn:
        conn.execute("INSERT INTO accounts (email) VALUES (?)", (email,))
        conn.commit()
    return get_account(email)


def increment_usage(email: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE accounts SET requests_used = requests_used + 1 WHERE email = ?",
            (email,),
        )
        conn.commit()


# --- API-Keys (mehrere pro Account) ---
def list_keys(email: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM api_keys WHERE email = ? ORDER BY created_at", (email,)
        ).fetchall()
        return [dict(r) for r in rows]


def create_key(email: str, name: str) -> dict:
    api_key = "sk-" + secrets.token_hex(24)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO api_keys (email, name, api_key) VALUES (?, ?, ?)",
            (email, name, api_key),
        )
        conn.commit()
    return {"name": name, "api_key": api_key}


def delete_key(email: str, api_key: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM api_keys WHERE email = ? AND api_key = ?", (email, api_key)
        )
        conn.commit()
        return cur.rowcount > 0


def get_account_by_key(api_key: str):
    """Liefert den Account (mit Tarif/Nutzung), zu dem ein Key gehoert."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT accounts.* FROM accounts
            JOIN api_keys ON api_keys.email = accounts.email
            WHERE api_keys.api_key = ?
            """,
            (api_key,),
        ).fetchone()
        return dict(row) if row else None
        
