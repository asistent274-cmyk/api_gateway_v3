import sqlite3
import secrets
from contextlib import contextmanager

DB_PATH = "gateway.db"

# Tages-Limits pro Tarif (None = unbegrenzt)
TIER_LIMITS = {
    "free": 35,
    "plus": 200,
    "pro": 1000,
    "owner": None,
}


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
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                tier TEXT NOT NULL DEFAULT 'free',   -- 'free' | 'plus' | 'pro' | 'owner'
                requests_used INTEGER NOT NULL DEFAULT 0,
                last_reset TEXT DEFAULT (date('now')),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def create_user(email: str, tier: str = "free") -> dict:
    api_key = "sk-" + secrets.token_hex(24)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (email, api_key, tier) VALUES (?, ?, ?)",
            (email, api_key, tier),
        )
        conn.commit()
    return get_user_by_email(email)


def get_user_by_email(email: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_key(api_key: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE api_key = ?", (api_key,)).fetchone()
        return dict(row) if row else None


def increment_usage(user_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET requests_used = requests_used + 1 WHERE id = ?",
            (user_id,),
        )
        conn.commit()


def reset_if_new_day(user_id: int):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE users
            SET requests_used = 0, last_reset = date('now')
            WHERE id = ? AND last_reset < date('now')
            """,
            (user_id,),
        )
        conn.commit()


def set_tier(email: str, tier: str):
    """Fuer manuelles Hochstufen eines Nutzers (spaeter durch Stripe-Webhook ersetzbar)."""
    if tier not in TIER_LIMITS:
        raise ValueError(f"Unbekannter Tarif: {tier}")
    with get_conn() as conn:
        conn.execute("UPDATE users SET tier = ? WHERE email = ?", (tier, email))
        conn.commit()
