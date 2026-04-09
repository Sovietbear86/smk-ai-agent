import json
from datetime import datetime

from sqlalchemy import bindparam, text

from app.db import engine


def get_session(session_id: str):
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT session_id, collected_data, booking_stage, lead_saved, updated_at, reminder_sent_at, visit_reminder_sent_at
                FROM sessions
                WHERE session_id = :sid
                """
            ),
            {"sid": session_id},
        ).fetchone()

        if not result:
            return {}

        return {
            "collected_data": json.loads(result[1] or "{}"),
            "booking_stage": result[2],
            "lead_saved": bool(result[3]),
            "updated_at": result[4],
            "reminder_sent_at": result[5],
            "visit_reminder_sent_at": result[6],
        }


def save_session(session_id: str, data: dict):
    updated_at = data.get("updated_at") or datetime.utcnow().isoformat()
    reminder_sent_at = data.get("reminder_sent_at")
    visit_reminder_sent_at = data.get("visit_reminder_sent_at")
    clear_reminder_sent_at = bool(data.get("clear_reminder_sent_at"))

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO sessions (
                    session_id,
                    collected_data,
                    booking_stage,
                    lead_saved,
                    updated_at,
                    reminder_sent_at,
                    visit_reminder_sent_at
                )
                VALUES (:sid, :data, :stage, :lead_saved, :updated_at, :reminder_sent_at, :visit_reminder_sent_at)
                ON CONFLICT(session_id) DO UPDATE SET
                    collected_data = excluded.collected_data,
                    booking_stage = excluded.booking_stage,
                    lead_saved = excluded.lead_saved,
                    updated_at = excluded.updated_at,
                    reminder_sent_at = CASE
                        WHEN :clear_reminder_sent_at = 1 THEN NULL
                        ELSE COALESCE(excluded.reminder_sent_at, sessions.reminder_sent_at)
                    END,
                    visit_reminder_sent_at = COALESCE(excluded.visit_reminder_sent_at, sessions.visit_reminder_sent_at)
                """
            ),
            {
                "sid": session_id,
                "data": json.dumps(data.get("collected_data", {}), ensure_ascii=False),
                "stage": data.get("booking_stage"),
                "lead_saved": int(data.get("lead_saved", False)),
                "updated_at": updated_at,
                "reminder_sent_at": reminder_sent_at,
                "visit_reminder_sent_at": visit_reminder_sent_at,
                "clear_reminder_sent_at": int(clear_reminder_sent_at),
            },
        )
        conn.commit()


def get_incomplete_sessions(booking_stages: list[str], older_than_iso: str) -> list[dict]:
    query = text(
        """
                SELECT session_id, collected_data, booking_stage, lead_saved, updated_at, reminder_sent_at
                     , visit_reminder_sent_at
                FROM sessions
                WHERE booking_stage IN :stages
                  AND lead_saved = 0
          AND updated_at <= :older_than
          AND reminder_sent_at IS NULL
        """
    ).bindparams(bindparam("stages", expanding=True))

    with engine.connect() as conn:
        result = conn.execute(
            query,
            {"stages": tuple(booking_stages), "older_than": older_than_iso},
        ).fetchall()

    sessions = []
    for row in result:
        sessions.append(
            {
                "session_id": row[0],
                "collected_data": json.loads(row[1] or "{}"),
                "booking_stage": row[2],
                "lead_saved": bool(row[3]),
                "updated_at": row[4],
                "reminder_sent_at": row[5],
                "visit_reminder_sent_at": row[6],
            }
        )
    return sessions


def mark_reminder_sent(session_id: str, sent_at: str | None = None):
    sent_at = sent_at or datetime.utcnow().isoformat()
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                UPDATE sessions
                SET reminder_sent_at = :sent_at
                WHERE session_id = :sid
                """
            ),
            {"sid": session_id, "sent_at": sent_at},
        )
        conn.commit()


def get_confirmed_sessions() -> list[dict]:
    query = text(
        """
        SELECT session_id, collected_data, booking_stage, lead_saved, updated_at, reminder_sent_at, visit_reminder_sent_at
        FROM sessions
        WHERE booking_stage = 'ready'
          AND lead_saved = 1
        """
    )

    with engine.connect() as conn:
        result = conn.execute(query).fetchall()

    sessions = []
    for row in result:
        sessions.append(
            {
                "session_id": row[0],
                "collected_data": json.loads(row[1] or "{}"),
                "booking_stage": row[2],
                "lead_saved": bool(row[3]),
                "updated_at": row[4],
                "reminder_sent_at": row[5],
                "visit_reminder_sent_at": row[6],
            }
        )
    return sessions


def mark_visit_reminder_sent(session_id: str, sent_at: str | None = None):
    sent_at = sent_at or datetime.utcnow().isoformat()
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                UPDATE sessions
                SET visit_reminder_sent_at = :sent_at
                WHERE session_id = :sid
                """
            ),
            {"sid": session_id, "sent_at": sent_at},
        )
        conn.commit()


def link_telegram_chat_to_contact(contact: str, chat_id: str, username: str | None = None) -> list[str]:
    if not contact or not chat_id:
        return []

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT session_id, collected_data
                FROM sessions
                """
            )
        ).fetchall()

        linked_sessions: list[str] = []
        for session_id, raw_data in rows:
            collected_data = json.loads(raw_data or "{}")
            if (collected_data.get("contact") or "").strip().lower() != contact.strip().lower():
                continue

            collected_data["telegram_chat_id"] = str(chat_id)
            if username:
                collected_data["telegram_username"] = username

            conn.execute(
                text(
                    """
                    UPDATE sessions
                    SET collected_data = :data,
                        updated_at = :updated_at
                    WHERE session_id = :sid
                    """
                ),
                {
                    "sid": session_id,
                    "data": json.dumps(collected_data, ensure_ascii=False),
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
            linked_sessions.append(session_id)

        conn.commit()

    return linked_sessions
