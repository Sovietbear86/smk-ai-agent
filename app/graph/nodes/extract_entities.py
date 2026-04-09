import re


BRAND_ALIASES = {
    "Honda": [
        "honda", "хонда", "голда", "gold wing", "goldwing", "gl", "vfr", "вуфер",
    ],
    "Yamaha": [
        "yamaha", "ямаха", "fjr", "фужер", "super tenere", "supertenere", "сутенер",
    ],
    "Suzuki": [
        "suzuki", "сузуки", "суза",
    ],
    "Kawasaki": [
        "kawasaki", "кавасаки", "кавас", "версус", "versys",
    ],
    "BMW": [
        "bmw", "бмв", "gs", "гусь", "гантеля", "k1600gtl", "k1600",
    ],
    "Ducati": [
        "ducati", "дукати", "multistrada", "мультистрада", "мультистрадания",
    ],
    "KTM": [
        "ktm", "ктм",
    ],
    "Triumph": [
        "triumph", "триумф",
    ],
    "Aprilia": [
        "aprilia", "априлия",
    ],
    "Harley-Davidson": [
        "harley", "harley-davidson", "харлей",
    ],
    "Indian": [
        "indian", "индиан",
    ],
}

MODEL_HINTS = {
    "голда": "Gold Wing",
    "gold wing": "Gold Wing",
    "goldwing": "Gold Wing",
    "gl": "Gold Wing",
    "vfr": "VFR",
    "вуфер": "VFR",
    "версус": "Versys",
    "versys": "Versys",
    "fjr": "FJR1300",
    "фужер": "FJR1300",
    "super tenere": "Super Tenere",
    "supertenere": "Super Tenere",
    "сутенер": "Super Tenere",
    "gs": "GS",
    "гусь": "GS",
    "гантеля": "K1600GTL",
    "k1600gtl": "K1600GTL",
    "k1600": "K1600GTL",
    "multistrada": "Multistrada",
    "мультистрада": "Multistrada",
    "мультистрадания": "Multistrada",
}

MODEL_ALIASES = {
    "голда": "Gold Wing",
    "gold": "Gold Wing",
    "goldwing": "Gold Wing",
    "gold wing": "Gold Wing",
    "gl": "Gold Wing",
    "vfr": "VFR",
    "вуфер": "VFR",
    "версус": "Versys",
    "versys": "Versys",
    "fjr": "FJR1300",
    "фужер": "FJR1300",
    "super tenere": "Super Tenere",
    "supertenere": "Super Tenere",
    "сутенер": "Super Tenere",
    "gs": "GS",
    "гусь": "GS",
    "гантеля": "K1600GTL",
    "k1600gtl": "K1600GTL",
    "k1600": "K1600GTL",
    "multistrada": "Multistrada",
    "мультистрада": "Multistrada",
    "мультистрадания": "Multistrada",
}


def _find_make_and_alias(lower_text: str):
    for make, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            if alias in lower_text:
                return make, alias
    return None, None


def _extract_model(text: str, lower_text: str, matched_alias: str | None):
    if not matched_alias:
        return None

    hint = MODEL_HINTS.get(matched_alias)
    if hint:
        return hint

    alias_pattern = re.escape(matched_alias)
    model_match = re.search(
        rf"{alias_pattern}\s+([A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9\-_\/]*)",
        text,
        re.IGNORECASE,
    )
    if model_match:
        candidate = model_match.group(1).strip(" ,.")
        if not re.fullmatch(r"(19\d{2}|20\d{2})", candidate):
            return candidate

    # Fallback for patterns like "владею вуфером 1200" or short nicknames in sentence.
    trailing_match = re.search(
        rf"{alias_pattern}[^\w]{{0,3}}([A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9\-_\/]*)",
        lower_text,
        re.IGNORECASE,
    )
    if trailing_match:
        candidate = trailing_match.group(1).strip(" ,.")
        if not re.fullmatch(r"(19\d{2}|20\d{2})", candidate):
            return candidate.upper() if re.search(r"[a-z]", candidate) else candidate

    return None


def _normalize_model(model: str | None) -> str | None:
    if not model:
        return None

    lowered = model.lower().strip()
    normalized = MODEL_ALIASES.get(lowered)
    if normalized:
        return normalized

    return model


def extract_entities(state):
    text = state["user_message"]
    lower_text = text.lower()

    entities = {}

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    if year_match:
        entities["year"] = year_match.group(1)

    found_make, matched_alias = _find_make_and_alias(lower_text)
    if found_make:
        entities["make"] = found_make

    model = _extract_model(text, lower_text, matched_alias)
    if model:
        entities["model"] = _normalize_model(model)

    phone_match = re.search(r"(\+?\d[\d\-\s]{8,}\d)", text)
    if phone_match:
        phone_candidate = phone_match.group(1).strip()
        digits_only = re.sub(r"\D", "", phone_candidate)
        if len(digits_only) >= 10:
            entities["contact"] = phone_candidate

    tg_match = re.search(r"@([A-Za-z0-9_]{4,})", text)
    if tg_match:
        entities["contact"] = "@" + tg_match.group(1)
        entities["contact_type"] = "telegram"

    if "whatsapp" in lower_text:
        entities["contact_type"] = "whatsapp"

    return {"entities": entities}
