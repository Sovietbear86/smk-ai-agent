from datetime import datetime, timedelta

from app.integrations.telegram_bot import telegram_bot
from app.services.availability_service import parse_slot_date, parse_slot_time
from app.services.session_service import (
    get_confirmed_sessions,
    get_incomplete_sessions,
    mark_reminder_sent,
    mark_visit_reminder_sent,
)


REMINDER_STAGES = {"need_contact", "offer_slots"}


def _format_admin_reminder(session: dict) -> str:
    data = session.get("collected_data", {}) or {}
    make = data.get("make", "-")
    model = data.get("model", "-")
    year = data.get("year", "-")
    goal = data.get("goal", "-")
    contact = data.get("contact", "-")
    selected_slot = data.get("selected_slot", "-")

    return (
        "Незавершенная запись\n\n"
        f"Session: {session.get('session_id')}\n"
        f"Этап: {session.get('booking_stage')}\n"
        f"Мотоцикл: {make} {model} {year}\n"
        f"Запрос: {goal}\n"
        f"Контакт: {contact}\n"
        f"Слот: {selected_slot}\n"
        f"Последняя активность: {session.get('updated_at')}\n"
        "Нужно напомнить пользователю завершить запись."
    )


def _format_user_reminder(session: dict) -> str:
    data = session.get("collected_data", {}) or {}
    goal = data.get("goal", "запись")
    return (
        f"Напоминаем про вашу заявку на {goal}. "
        "Если хотите продолжить запись, просто ответьте удобной датой или временем."
    )


def _format_visit_reminder(session: dict) -> str:
    data = session.get("collected_data", {}) or {}
    selected_slot = data.get("selected_slot", "-")
    goal = data.get("goal", "визит")
    make = " ".join(
        part for part in [data.get("make"), data.get("model"), data.get("year")] if part
    ).strip() or "мотоцикл"
    return (
        f"Напоминаем: вы записаны к нам через сутки.\n\n"
        f"Мотоцикл: {make}\n"
        f"Запрос: {goal}\n"
        f"Слот: {selected_slot}\n\n"
        "Если планы изменились, просто ответьте на это сообщение или свяжитесь с нами заранее."
    )


def _send_session_message(session: dict, user_message: str, admin_message: str) -> dict:
    data = session.get("collected_data", {}) or {}
    direct_chat_id = data.get("telegram_chat_id")

    if direct_chat_id:
        return telegram_bot.send_text_to_chat(direct_chat_id, user_message)
    return telegram_bot.send_text(admin_message)


def send_incomplete_booking_reminders(older_than_minutes: int = 60) -> dict:
    threshold = (datetime.utcnow() - timedelta(minutes=older_than_minutes)).isoformat()
    sessions = get_incomplete_sessions(sorted(REMINDER_STAGES), threshold)

    sent = 0
    results = []

    for session in sessions:
        result = _send_session_message(
            session,
            _format_user_reminder(session),
            _format_admin_reminder(session),
        )

        if result.get("ok"):
            mark_reminder_sent(session["session_id"])
            sent += 1

        results.append(
            {
                "session_id": session["session_id"],
                "booking_stage": session["booking_stage"],
                "result": result,
            }
        )

    return {
        "ok": True,
        "checked": len(sessions),
        "sent": sent,
        "results": results,
    }


def _parse_selected_slot_start(selected_slot: str | None) -> datetime | None:
    if not selected_slot:
        return None

    parts = selected_slot.strip().split()
    if len(parts) < 2:
        return None

    slot_date = parse_slot_date(parts[0])
    time_range = parts[1]
    start_time_value = time_range.split("-", 1)[0]
    start_time = parse_slot_time(start_time_value)
    if not slot_date or not start_time:
        return None

    return datetime.combine(slot_date, start_time)


def send_visit_reminders(window_start_hours: int = 23, window_end_hours: int = 25) -> dict:
    now = datetime.utcnow()
    lower_bound = now + timedelta(hours=window_start_hours)
    upper_bound = now + timedelta(hours=window_end_hours)

    checked = 0
    sent = 0
    results = []

    for session in get_confirmed_sessions():
        checked += 1
        if session.get("visit_reminder_sent_at"):
            continue

        data = session.get("collected_data", {}) or {}
        visit_dt = _parse_selected_slot_start(data.get("selected_slot"))
        if visit_dt is None:
            continue

        if not (lower_bound <= visit_dt <= upper_bound):
            continue

        result = _send_session_message(
            session,
            _format_visit_reminder(session),
            "Подтвержденная запись на завтра, но нет прямого Telegram chat_id у клиента.\n\n"
            f"Session: {session.get('session_id')}\n"
            f"Контакт: {data.get('contact', '-')}\n"
            f"Слот: {data.get('selected_slot', '-')}",
        )

        if result.get("ok"):
            mark_visit_reminder_sent(session["session_id"])
            sent += 1

        results.append(
            {
                "session_id": session["session_id"],
                "selected_slot": data.get("selected_slot"),
                "result": result,
            }
        )

    return {
        "ok": True,
        "checked": checked,
        "sent": sent,
        "window_start_hours": window_start_hours,
        "window_end_hours": window_end_hours,
        "results": results,
    }
