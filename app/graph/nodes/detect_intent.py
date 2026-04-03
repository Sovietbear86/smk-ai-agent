import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ALLOWED = {"dyno", "afr", "ecu", "diagnostics", "pricing", "booking", "contacts", "other"}

def detect_intent(state):
    message = state["user_message"]
    text = message.lower()

    if any(x in text for x in ["запис", "запись", "приехать", "визит"]):
        return {"intent": "booking"}
    if any(x in text for x in ["сколько стоит", "цена", "стоимость"]):
        return {"intent": "pricing"}
    if any(x in text for x in ["afr", "смесь"]):
        return {"intent": "afr"}
    if any(x in text for x in ["ecu", "прошив", "flash"]):
        return {"intent": "ecu"}
    if any(x in text for x in ["диностенд", "power run", "замер мощности"]):
        return {"intent": "dyno"}
    if any(x in text for x in ["плохо едет", "нет тяги", "провал", "диагност"]):
        return {"intent": "diagnostics"}

    prompt = f"""
Определи intent сообщения пользователя.

Варианты:
- dyno
- afr
- ecu
- diagnostics
- pricing
- booking
- contacts
- other

Сообщение: {message}

Ответь только одним словом.
"""
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    intent = response.choices[0].message.content.strip().lower()
    if intent not in ALLOWED:
        intent = "other"

    return {"intent": intent}