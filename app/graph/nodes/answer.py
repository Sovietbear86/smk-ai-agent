import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

from app.services.knowledge_service import knowledge_service


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Ты ассистент SMK Performance Lab.

Твоя задача:
- отвечать кратко и по делу
- звучать как специалист по диностенду и настройке мотоциклов
- не выдумывать цены
- не обещать прирост мощности
- после ответа задавать максимум 1 уточняющий вопрос
"""


def build_fallback_answer(intent: str) -> str:
    if intent == "booking":
        return "Помогу с записью. Напишите марку, модель и год мотоцикла, а также удобный контакт."
    if intent == "pricing":
        return "По стоимости смогу сориентировать после уточнения мотоцикла и задачи."
    if intent in {"ecu", "dyno", "afr", "diagnostics"}:
        return "Помогу разобраться. Опишите мотоцикл и задачу чуть подробнее."
    if intent == "contacts":
        return "Могу помочь с записью. Напишите удобный контакт для связи."
    return "Уточните, пожалуйста, что именно нужно: запись, настройка ECU, диагностика или замер на стенде."


def answer(state):
    prebuilt_answer = state.get("answer")
    if prebuilt_answer:
        return {"answer": prebuilt_answer}

    message = state["user_message"]
    intent = state.get("intent", "other")
    entities = state.get("entities", {})
    collected = state.get("collected_data", {})

    kb = knowledge_service.find_answer(message)
    if kb:
        response_text = kb["answer"]
        if kb["followup"]:
            response_text += "\n\n" + kb["followup"]
        return {"answer": response_text}

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"""
Сообщение пользователя: {message}
Intent: {intent}
Entities: {entities}
Collected data: {collected}

Сформируй короткий профессиональный ответ на русском языке.
""",
                },
            ],
            temperature=0.3,
        )
        return {"answer": response.choices[0].message.content.strip()}
    except Exception as exc:
        logger.warning("OpenAI answer generation failed, using fallback answer: %s", exc)
        return {"answer": build_fallback_answer(intent)}
