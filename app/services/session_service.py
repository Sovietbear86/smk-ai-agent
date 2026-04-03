import json
from sqlalchemy import text
from app.db import engine


def get_session(session_id: str):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM sessions WHERE session_id = :sid"),
            {"sid": session_id}
        ).fetchone()

        if not result:
            return {}

        return {
            "collected_data": json.loads(result[1] or "{}"),
            "booking_stage": result[2],
            "lead_saved": bool(result[3]),
        }


def save_session(session_id: str, data: dict):
    with engine.connect() as conn:
        conn.execute(text("""
        INSERT INTO sessions (session_id, collected_data, booking_stage, lead_saved)
        VALUES (:sid, :data, :stage, :lead_saved)
        ON CONFLICT(session_id) DO UPDATE SET
            collected_data = excluded.collected_data,
            booking_stage = excluded.booking_stage,
            lead_saved = excluded.lead_saved
        """), {
            "sid": session_id,
            "data": json.dumps(data.get("collected_data", {})),
            "stage": data.get("booking_stage"),
            "lead_saved": int(data.get("lead_saved", False)),
        })
        conn.commit()