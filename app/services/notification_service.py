from app.integrations.telegram_bot import telegram_bot


def format_lead_message(lead: dict) -> str:
    data = lead.get("data", {})

    make = data.get("make", "-")
    model = data.get("model", "-")
    year = data.get("year", "-")
    goal = data.get("goal", "-")
    contact = data.get("contact", "-")
    selected_slot = data.get("selected_slot", "-")
    booked_slot_id = data.get("booked_slot_id", "-")
    if data.get("callback_requested"):
        selected_slot = "TBD/"

    text = (
        "Новая заявка с сайта\n\n"
        f"Lead ID: {lead.get('id')}\n"
        f"Session: {lead.get('session_id')}\n"
        f"Мотоцикл: {make} {model} {year}\n"
        f"Запрос: {goal}\n"
        f"Контакт: {contact}\n"
        f"Слот: {selected_slot}\n"
        f"Slot ID: {booked_slot_id}\n"
        f"Создано: {lead.get('created_at')}"
    )
    return text


def notify_new_lead(lead: dict) -> dict:
    message = format_lead_message(lead)
    return telegram_bot.send_text(message)
