import json
from datetime import datetime
from sqlalchemy import text
from app.db import engine


def create_lead(session_id: str, collected_data: dict):
    """
    Создает новый лид в базе данных
    """
    with engine.connect() as conn:
        result = conn.execute(text("""
        INSERT INTO leads (session_id, data, created_at)
        VALUES (:sid, :data, :created_at)
        RETURNING id
        """), {
            "sid": session_id,
            "data": json.dumps(collected_data, ensure_ascii=False),
            "created_at": datetime.utcnow().isoformat()
        })

        lead_id = result.fetchone()[0]
        conn.commit()

        return {
            "id": lead_id,
            "session_id": session_id,
            "data": collected_data,
            "created_at": datetime.utcnow().isoformat()
        }


def get_all_leads(limit: int = 50):
    """
    Возвращает список последних лидов (для дебага / будущей админки)
    """
    with engine.connect() as conn:
        result = conn.execute(text("""
        SELECT id, session_id, data, created_at
        FROM leads
        ORDER BY id DESC
        LIMIT :limit
        """), {"limit": limit}).fetchall()

        leads = []
        for row in result:
            leads.append({
                "id": row[0],
                "session_id": row[1],
                "data": json.loads(row[2]),
                "created_at": row[3]
            })

        return leads


def get_lead_by_id(lead_id: int):
    """
    Получить конкретный лид по ID
    """
    with engine.connect() as conn:
        result = conn.execute(text("""
        SELECT id, session_id, data, created_at
        FROM leads
        WHERE id = :id
        """), {"id": lead_id}).fetchone()

        if not result:
            return None

        return {
            "id": result[0],
            "session_id": result[1],
            "data": json.loads(result[2]),
            "created_at": result[3]
        }