
from app.services.knowledge_service import knowledge_service
import os
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


client = OpenAI()

SYSTEM_PROMPT = """
Ты ассистент SMK Performance Lab.

Твоя задача:
- отвечать кратко и по делу
- звучать как специалист по диностенду и настройке мотоциклов
- не выдумывать цены
- не обещать прирост мощности
- после ответа задавать максимум 1 уточняющий вопрос
"""

def answer(state):
    # если qualification уже подготовил ответ — используем его
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
"""
            }
        ],
        temperature=0.3
    )

    return {"answer": response.choices[0].message.content.strip()}