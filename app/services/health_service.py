import os

from openai import OpenAI

from app.integrations.google_sheets import read_slots
from app.integrations.telegram_bot import telegram_bot


def check_openai() -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        return {"ok": False, "error": "OPENAI_API_KEY is not configured"}

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "Reply with OK"}],
            temperature=0,
        )
        return {
            "ok": True,
            "model": "gpt-4.1-mini",
            "reply": (response.choices[0].message.content or "").strip(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_google_sheets() -> dict:
    try:
        slots = read_slots()
        free_slots = [slot for slot in slots if slot.get("status", "").lower() == "free"]
        return {
            "ok": True,
            "slots_count": len(slots),
            "free_slots_count": len(free_slots),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_telegram() -> dict:
    result = telegram_bot.get_me()
    if not result.get("ok"):
        return result

    bot = result.get("result", {})
    return {
        "ok": True,
        "bot_id": bot.get("id"),
        "username": bot.get("username"),
    }
