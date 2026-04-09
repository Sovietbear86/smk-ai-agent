import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")


class TelegramBot:
    def __init__(self, bot_token: str | None, admin_chat_id: str | None, webhook_secret: str | None = None):
        self.bot_token = bot_token
        self.admin_chat_id = admin_chat_id
        self.webhook_secret = webhook_secret

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.admin_chat_id)

    def send_text_to_chat(self, chat_id: str | int | None, text: str) -> dict:
        if not self.bot_token or not chat_id:
            return {"ok": False, "error": "telegram is not configured"}

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
        }

        try:
            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                logger.warning("Telegram API returned non-ok response: %s", result)
            return result
        except requests.RequestException as exc:
            logger.exception("Telegram send failed")
            return {"ok": False, "error": str(exc)}

    def send_text(self, text: str) -> dict:
        return self.send_text_to_chat(self.admin_chat_id, text)

    def get_me(self) -> dict:
        if not self.enabled:
            return {"ok": False, "error": "telegram is not configured"}

        url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                logger.warning("Telegram getMe returned non-ok response: %s", result)
            return result
        except requests.RequestException as exc:
            logger.exception("Telegram getMe failed")
            return {"ok": False, "error": str(exc)}


telegram_bot = TelegramBot(BOT_TOKEN, ADMIN_CHAT_ID, WEBHOOK_SECRET)
