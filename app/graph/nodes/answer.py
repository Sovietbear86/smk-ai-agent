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
- отвечать кратко, спокойно и по делу
- помогать по записи, настройке ECU, диностенду и диагностике мотоциклов
- не выдумывать цены и технические факты
- не задавать клиенту узкоспециальные вопросы, которые обычный владелец мотоцикла обычно не знает
- не спрашивать про дампы прошивки, карты, полную калибровку, версии софта, логи, AFR-таблицы и другие технические детали
- если вопрос не по теме сервиса, ответить коротко и мягко вернуть разговор к записи или сути обращения
- если пользователь продолжает оффтоп несколько сообщений подряд, вежливо сказать, что это вне зоны ответственности ассистента
- если пользователь матерится или агрессирует, вежливо завершить диалог фразой в духе: если все-таки запланируете воспользоваться услугами сервиса, будем рады вас видеть
- после ответа задавать максимум 1 простой вопрос, который продвигает к записи
"""

PROFANITY_TOKENS = {
    "бляд", "блять", "сука", "нахуй", "на хуй", "хуй", "хуйн", "еб", "ёб",
    "пизд", "мраз", "твар", "мудак", "долбоеб", "долбоёб", "пошел нах",
    "охуел", "оху", "уеб", "уёб",
}

SERVICE_TOPICS = {
    "ecu", "dyno", "afr", "diagnostics", "booking", "pricing", "contacts",
}


def is_abusive(message: str) -> bool:
    lowered = (message or "").lower()
    return any(token in lowered for token in PROFANITY_TOKENS)


def build_fallback_answer(intent: str) -> str:
    if intent in {"booking", "ecu", "dyno", "afr", "diagnostics"}:
        return "Помогу с записью. Напишите марку, модель и год мотоцикла, а также что хотите сделать."
    if intent == "pricing":
        return "По стоимости смогу сориентировать после уточнения мотоцикла и задачи."
    if intent == "contacts":
        return "Могу помочь с записью. Напишите удобный контакт для связи."
    return "Помогу по вопросам записи, настройки ECU, диностенда и диагностики. Если хотите, сразу напишите мотоцикл и задачу."


def build_offtopic_answer(collected: dict, off_topic_count: int) -> str:
    if off_topic_count >= 2:
        return "Этот вопрос уже вне зоны ответственности ассистента. Если все-таки захотите записаться на настройку, замер или диагностику, буду рад помочь."

    if collected.get("make") or collected.get("goal"):
        return "Могу помочь именно по услугам сервиса и записи. Если хотите продолжить, напишите, что нужно сделать с мотоциклом или какое время вам удобно."

    return "Могу помочь по услугам сервиса: настройка ECU, диностенд, диагностика и запись. Если хотите, сразу напишите марку, модель, год и задачу."


def build_abuse_answer() -> str:
    return "На этом остановлю диалог. Если все-таки запланируете воспользоваться услугами нашего сервиса, будем рады вас видеть."


def answer(state):
    prebuilt_answer = state.get("answer")
    if prebuilt_answer:
        return {"answer": prebuilt_answer}

    message = state["user_message"]
    intent = state.get("intent", "other")
    entities = state.get("entities", {})
    collected = state.get("collected_data", {}).copy()
    booking_stage = state.get("booking_stage", "not_started")

    if collected.get("conversation_closed") == "abuse":
        return {"answer": build_abuse_answer(), "collected_data": collected}

    if is_abusive(message):
        collected["conversation_closed"] = "abuse"
        return {"answer": build_abuse_answer(), "collected_data": collected}

    kb = knowledge_service.find_answer(message)
    if kb:
        response_text = kb["answer"]
        if kb["followup"]:
            response_text += "\n\n" + kb["followup"]
        return {"answer": response_text, "collected_data": collected}

    if intent == "other" and booking_stage == "not_started":
        off_topic_count = int(collected.get("off_topic_count", 0)) + 1
        collected["off_topic_count"] = off_topic_count
        return {
            "answer": build_offtopic_answer(collected, off_topic_count),
            "collected_data": collected,
        }

    collected["off_topic_count"] = 0

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
Booking stage: {booking_stage}
Entities: {entities}
Collected data: {collected}

Если intent относится к услугам сервиса, веди пользователя к простой записи.
Если данных не хватает, спрашивай только простые вещи: мотоцикл, задача, контакт, удобное время.
Сформируй короткий профессиональный ответ на русском языке.
""",
                },
            ],
            temperature=0.2,
        )
        return {
            "answer": response.choices[0].message.content.strip(),
            "collected_data": collected,
        }
    except Exception as exc:
        logger.warning("OpenAI answer generation failed, using fallback answer: %s", exc)
        return {"answer": build_fallback_answer(intent), "collected_data": collected}
