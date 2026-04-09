from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from app.db import engine


def _ensure_column(conn, table_name: str, column_name: str, column_type: str):
    columns = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    column_names = {row[1] for row in columns}
    if column_name not in column_names:
        try:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
        except OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise


def init_db():
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            collected_data TEXT,
            booking_stage TEXT,
            lead_saved INTEGER
        )
        """))
        _ensure_column(conn, "sessions", "updated_at", "TEXT")
        _ensure_column(conn, "sessions", "reminder_sent_at", "TEXT")
        _ensure_column(conn, "sessions", "visit_reminder_sent_at", "TEXT")

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            data TEXT,
            created_at TEXT
        )
        """))

        conn.commit()
