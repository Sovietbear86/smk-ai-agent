import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")


class TelegramBot:
    def __init__(self, bot_token: str | None, admin_chat_id: str | None):
        self.bot_token = bot_token
        self.admin_chat_id = admin_chat_id

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.admin_chat_id)

    def send_text(self, text: str) -> dict:
        if not self.enabled:
            return {"ok": False, "error": "telegram is not configured"}

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.admin_chat_id,
            "text": text,
        }

        response = requests.post(url, json=payload, timeout=20)
        return response.json()


telegram_bot = TelegramBot(BOT_TOKEN, ADMIN_CHAT_ID)