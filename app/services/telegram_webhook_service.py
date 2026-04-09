from app.integrations.telegram_bot import telegram_bot
from app.services.session_service import link_telegram_chat_to_contact


def process_telegram_update(update: dict) -> dict:
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    text = (message.get("text") or "").strip()
    chat_id = chat.get("id")
    username = (chat.get("username") or message.get("from", {}).get("username") or "").strip()

    if not chat_id:
        return {"ok": True, "ignored": True, "reason": "no chat id"}

    contact = f"@{username}" if username else ""
    linked_sessions = link_telegram_chat_to_contact(contact, str(chat_id), username=username or None) if contact else []

    if linked_sessions:
        reply = (
            "Telegram привязан. Если вы не завершили запись, "
            "сможем напомнить вам здесь."
        )
    elif text.startswith("/start"):
        reply = (
            "Бот подключен. Если при записи на сайте вы оставите этот Telegram, "
            "мы сможем прислать сюда напоминание."
        )
    else:
        reply = "Соединение с Telegram активно."

    telegram_result = telegram_bot.send_text_to_chat(chat_id, reply)

    return {
        "ok": True,
        "chat_id": str(chat_id),
        "username": username or None,
        "linked_sessions": linked_sessions,
        "telegram_result": telegram_result,
    }
