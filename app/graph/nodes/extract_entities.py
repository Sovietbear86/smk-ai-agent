import re


def extract_entities(state):
    text = state["user_message"]
    lower_text = text.lower()

    entities = {}

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    if year_match:
        entities["year"] = year_match.group(1)

    brands = [
        "honda", "yamaha", "suzuki", "kawasaki", "bmw",
        "ducati", "ktm", "triumph", "aprilia"
    ]

    found_make = None
    for brand in brands:
        if brand in lower_text:
            found_make = brand.title()
            entities["make"] = found_make
            break

    if found_make:
        model_match = re.search(found_make + r"\s+([A-Za-z0-9\-\_]+)", text, re.IGNORECASE)
        if model_match:
            entities["model"] = model_match.group(1)

    phone_match = re.search(r"(\+?\d[\d\-\s]{7,}\d)", text)
    if phone_match:
        entities["contact"] = phone_match.group(1).strip()

    tg_match = re.search(r"@([A-Za-z0-9_]{4,})", text)
    if tg_match:
        entities["contact"] = "@" + tg_match.group(1)
        entities["contact_type"] = "telegram"

    if "whatsapp" in lower_text:
        entities["contact_type"] = "whatsapp"

    return {"entities": entities}