from sqlalchemy import text
from app.db import engine


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

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            data TEXT,
            created_at TEXT
        )
        """))

        conn.commit()