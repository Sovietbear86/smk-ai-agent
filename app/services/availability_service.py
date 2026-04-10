import logging
import os
import re
import json
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from openai import OpenAI

from app.integrations.google_sheets import append_slot, read_slots, update_slot_status


load_dotenv()
logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

WEEKDAYS = {
    "понедельник": 0,
    "вторник": 1,
    "среда": 2,
    "среду": 2,
    "четверг": 3,
    "пятница": 4,
    "пятницу": 4,
    "суббота": 5,
    "субботу": 5,
    "воскресенье": 6,
    "воскресенье": 6,
}

TIME_BUCKETS = {
    "утро": (6, 12),
    "утром": (6, 12),
    "на утро": (6, 12),
    "день": (12, 17),
    "днем": (12, 17),
    "днём": (12, 17),
    "на день": (12, 17),
    "обед": (12, 15),
    "в обед": (12, 15),
    "вечер": (17, 22),
    "вечером": (17, 22),
    "на вечер": (17, 22),
}

CANCEL_PATTERNS = {
    "отмена",
    "отменить",
    "отменяю",
    "не надо",
    "не нужно",
    "передумал",
    "передумала",
}

CHANGE_SLOT_PATTERNS = (
    "другой слот",
    "изменить слот",
    "поменять слот",
    "сменить слот",
    "другое время",
    "другую дату",
    "перенести запись",
    "перенос",
)

SLOT_PREFERENCE_TOKENS = (
    "сегодня", "завтра", "послезавтра", "понедель", "вторник", "сред", "четверг",
    "пятниц", "суббот", "воскрес", "утр", "дн", "вечер", "обед", "после",
    "до ", "первая половина", "вторая половина", "выходн", "майск", "праздник",
    "час", "январ", "феврал", "март", "апрел",
    "мая", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр",
)

CONSULTATION_REQUEST_PATTERNS = (
    "консультац",
    "перезвоните",
    "перезвони",
    "свяжитесь",
    "свяжитесь со мной",
    "свяжитесь со мной позже",
    "свяжется специалист",
    "позже",
    "пока не готов",
    "пока не готов к записи",
    "не готов к записи",
    "сначала нужно получить ответ",
    "сначала хочу задать вопрос",
    "сначала хочу получить ответ",
    "нужно получить ответ на вопрос",
    "есть вопрос",
    "есть пара вопросов",
)


def parse_slot_date(date_value: str) -> date | None:
    if not date_value:
        return None

    normalized = date_value.strip().replace("_", "-")
    try:
        return datetime.strptime(normalized, "%Y-%m-%d").date()
    except ValueError:
        return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_slot_time(value: str) -> time | None:
    if not value:
        return None

    normalized = value.strip()
    for fmt in ("%H:%M", "%H"):
        try:
            return datetime.strptime(normalized, fmt).time()
        except ValueError:
            continue
    return None


def slot_start_datetime(slot: dict) -> datetime | None:
    slot_date = parse_slot_date(str(slot.get("date", "")))
    start_time = parse_slot_time(str(slot.get("start_time", "")))
    if not slot_date or not start_time:
        return None
    return datetime.combine(slot_date, start_time)


def format_slot(slot: dict) -> str:
    return f"{slot.get('date')} {slot.get('start_time')}-{slot.get('end_time')}"


def _format_slot_for_ai(slot: dict) -> str:
    slot_dt = slot_start_datetime(slot)
    weekday = ""
    if slot_dt:
        weekday_names = [
            "понедельник",
            "вторник",
            "среда",
            "четверг",
            "пятница",
            "суббота",
            "воскресенье",
        ]
        weekday = weekday_names[slot_dt.weekday()]
    return (
        f"{slot.get('slot_id')}: {format_slot(slot)}"
        + (f" ({weekday})" if weekday else "")
    )


def _read_all_slots() -> list[dict]:
    try:
        return read_slots()
    except Exception as exc:
        logger.warning("Google Sheets slots read failed, continuing without slots: %s", exc)
        return []


def get_free_slots(limit: int | None = 5) -> list[dict]:
    free_slots = [
        slot
        for slot in _read_all_slots()
        if slot.get("status", "").lower() == "free"
    ]
    free_slots.sort(key=lambda item: slot_start_datetime(item) or datetime.max)
    if limit is None:
        return free_slots
    return free_slots[:limit]


def get_slot_by_id(slot_id: str | None) -> dict | None:
    if not slot_id:
        return None

    for slot in _read_all_slots():
        if slot.get("slot_id") == slot_id:
            return slot
    return None


def get_slots_by_ids(slot_ids: list[str] | None) -> list[dict]:
    if not slot_ids:
        return []

    order = {slot_id: idx for idx, slot_id in enumerate(slot_ids)}
    slots = [slot for slot in get_free_slots(limit=None) if slot.get("slot_id") in order]
    slots.sort(key=lambda slot: order.get(slot.get("slot_id"), 10**9))
    return slots


def get_slot_candidates(offered_slot_ids: list[str] | None = None) -> list[dict]:
    return get_slots_by_ids(offered_slot_ids) or get_free_slots(limit=None)


def parse_slot_choice(user_message: str, max_choice: int = 5) -> int | None:
    text = (user_message or "").strip().lower()
    if not text:
        return None

    if any(token in text for token in ["любой", "без разницы", "ближайший", "самый ранний", "любой вариант"]):
        return 0

    word_map = {
        1: ("1", "1.", "1)", "перв", "один", "одну"),
        2: ("2", "2.", "2)", "втор", "два", "две"),
        3: ("3", "3.", "3)", "трет", "три"),
        4: ("4", "4.", "4)", "четвер", "четыр"),
        5: ("5", "5.", "5)", "пят",),
    }

    for number in range(1, max_choice + 1):
        patterns = word_map.get(number, ())
        for pattern in patterns:
            if pattern.isdigit():
                if re.search(rf"\b{re.escape(pattern)}\b", text):
                    return number - 1
            elif pattern in text:
                return number - 1
    return None


def _extract_explicit_date(text: str, today: date) -> tuple[date | None, tuple[date, date] | None]:
    if not text:
        return None, None

    lowered = text.lower()

    iso_match = re.search(r"\b(20\d{2})[-_./](\d{1,2})[-_./](\d{1,2})\b", lowered)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        candidate = _safe_date(year, month, day)
        return candidate, None

    ru_numeric_match = re.search(r"\b(\d{1,2})[._/-](\d{1,2})(?:[._/-](20\d{2}))?\b", lowered)
    if ru_numeric_match:
        day = int(ru_numeric_match.group(1))
        month = int(ru_numeric_match.group(2))
        year = int(ru_numeric_match.group(3) or today.year)
        candidate = _safe_date(year, month, day)
        if candidate is None:
            return None, None
        if candidate < today:
            candidate = _safe_date(year + 1, month, day)
        return candidate, None

    text_month_match = re.search(
        r"\b(\d{1,2}|первого|второго|третьего|четвертого|четвёртого|пятого|шестого|седьмого|восьмого|девятого|десятого|одиннадцатого|двенадцатого|тринадцатого|четырнадцатого|пятнадцатого|шестнадцатого|семнадцатого|восемнадцатого|девятнадцатого|двадцатого|двадцать первого|двадцать первого|двадцать второго|двадцать третьего|двадцать четвертого|двадцать четвёртого|двадцать пятого|двадцать шестого|двадцать седьмого|двадцать восьмого|двадцать девятого|тридцатого|тридцать первого)\s+([а-я]+)",
        lowered,
    )
    if text_month_match:
        day_token = text_month_match.group(1).replace("ё", "е")
        month_token = text_month_match.group(2)
        day_lookup = {
            "первого": 1,
            "второго": 2,
            "третьего": 3,
            "четвертого": 4,
            "четвертого": 4,
            "пятого": 5,
            "шестого": 6,
            "седьмого": 7,
            "восьмого": 8,
            "девятого": 9,
            "десятого": 10,
            "одиннадцатого": 11,
            "двенадцатого": 12,
            "тринадцатого": 13,
            "четырнадцатого": 14,
            "пятнадцатого": 15,
            "шестнадцатого": 16,
            "семнадцатого": 17,
            "восемнадцатого": 18,
            "девятнадцатого": 19,
            "двадцатого": 20,
            "двадцать первого": 21,
            "двадцать второго": 22,
            "двадцать третьего": 23,
            "двадцать четвертого": 24,
            "двадцать пятого": 25,
            "двадцать шестого": 26,
            "двадцать седьмого": 27,
            "двадцать восьмого": 28,
            "двадцать девятого": 29,
            "тридцатого": 30,
            "тридцать первого": 31,
        }
        day = day_lookup.get(day_token, int(day_token) if day_token.isdigit() else None)
        month = MONTHS.get(month_token)
        if day and month:
            candidate = _safe_date(today.year, month, day)
            if candidate is None:
                return None, None
            if candidate < today:
                candidate = _safe_date(today.year + 1, month, day)
            return candidate, None

    if "сегодня" in lowered:
        return today, None
    if "завтра" in lowered:
        return today + timedelta(days=1), None
    if "послезавтра" in lowered:
        return today + timedelta(days=2), None

    for token, weekday in WEEKDAYS.items():
        if token in lowered:
            delta = (weekday - today.weekday()) % 7
            candidate = today + timedelta(days=delta or 7)
            return candidate, None

    if "выходн" in lowered:
        saturday_delta = (5 - today.weekday()) % 7
        saturday = today + timedelta(days=saturday_delta or 7)
        sunday = saturday + timedelta(days=1)
        return None, (saturday, sunday)

    if "майск" in lowered and "праздник" in lowered:
        year = today.year
        start = date(year, 5, 1)
        end = date(year, 5, 10)
        if end < today:
            start = date(year + 1, 5, 1)
            end = date(year + 1, 5, 10)
        return None, (start, end)

    return None, None


def _extract_time_preferences(text: str) -> dict:
    lowered = (text or "").lower()
    result = {
        "time_range": None,
        "preferred_hour": None,
        "after_hour": None,
        "before_hour": None,
    }

    for token, bucket in TIME_BUCKETS.items():
        if token in lowered:
            result["time_range"] = bucket
            break

    exact_time_match = re.search(r"\b(?:в|к)\s*(\d{1,2})(?::(\d{2}))?\b", lowered)
    if exact_time_match:
        result["preferred_hour"] = int(exact_time_match.group(1))

    after_match = re.search(r"\bпосле\s*(\d{1,2})(?::(\d{2}))?\b", lowered)
    if after_match:
        result["after_hour"] = int(after_match.group(1))

    before_match = re.search(r"\bдо\s*(\d{1,2})(?::(\d{2}))?\b", lowered)
    if before_match:
        result["before_hour"] = int(before_match.group(1))

    return result


def parse_slot_preference(user_message: str, today: date | None = None) -> dict:
    today = today or date.today()
    text = (user_message or "").strip()
    exact_date, date_range = _extract_explicit_date(text, today)
    time_preferences = _extract_time_preferences(text)

    return {
        "text": text,
        "exact_date": exact_date,
        "date_range": date_range,
        **time_preferences,
    }


def might_be_slot_preference_message(user_message: str) -> bool:
    text = (user_message or "").strip().lower()
    if not text:
        return False

    if parse_slot_choice(text, max_choice=5) is not None:
        return True

    if re.search(r"\b\d{1,2}[:.]\d{2}\b", text):
        return True
    if re.search(r"\b\d{1,2}[./-]\d{1,2}\b", text):
        return True
    if re.search(r"\b20\d{2}[./_-]\d{1,2}[./_-]\d{1,2}\b", text):
        return True

    return any(token in text for token in SLOT_PREFERENCE_TOKENS)


def has_meaningful_slot_preference(preference: dict) -> bool:
    return any(
        preference.get(key) is not None
        for key in ("exact_date", "date_range", "time_range", "preferred_hour", "after_hour", "before_hour")
    )


def _matches_direct_slot_reference(text: str, slot: dict) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return False

    candidates = {
        format_slot(slot).lower(),
        format_slot(slot).lower().replace("_", "-"),
        f"{slot.get('date')} {slot.get('start_time')} - {slot.get('end_time')}".lower(),
        str(slot.get("slot_id", "")).lower(),
        f"{slot.get('date')}".lower(),
    }
    start_time = str(slot.get("start_time", "")).lower()
    end_time = str(slot.get("end_time", "")).lower()
    if start_time and end_time and start_time in lowered and end_time in lowered:
        return True
    return any(candidate and candidate in lowered for candidate in candidates)


def score_slot_against_preference(slot: dict, preference: dict, now: datetime | None = None) -> float:
    now = now or datetime.now()
    slot_dt = slot_start_datetime(slot)
    if slot_dt is None:
        return float("inf")

    score = max((slot_dt - now).total_seconds() / 3600, 0) / 24

    exact_date = preference.get("exact_date")
    date_range = preference.get("date_range")
    time_range = preference.get("time_range")
    preferred_hour = preference.get("preferred_hour")
    after_hour = preference.get("after_hour")
    before_hour = preference.get("before_hour")

    slot_date = slot_dt.date()
    slot_hour = slot_dt.hour

    if exact_date:
        score += abs((slot_date - exact_date).days) * 10

    if date_range:
        start, end = date_range
        if slot_date < start:
            score += (start - slot_date).days * 10
        elif slot_date > end:
            score += (slot_date - end).days * 10

    if time_range:
        start_hour, end_hour = time_range
        if start_hour <= slot_hour < end_hour:
            score -= 1
        else:
            score += min(abs(slot_hour - start_hour), abs(slot_hour - end_hour)) * 2

    if preferred_hour is not None:
        score += abs(slot_hour - preferred_hour) * 1.5

    if after_hour is not None and slot_hour < after_hour:
        score += (after_hour - slot_hour) * 2

    if before_hour is not None and slot_hour > before_hour:
        score += (slot_hour - before_hour) * 2

    return score


def suggest_slots_for_preference(
    user_message: str,
    limit: int = 5,
    offered_slot_ids: list[str] | None = None,
) -> list[dict]:
    slots = get_slot_candidates(offered_slot_ids)
    if not slots:
        return []

    ai_slots = suggest_slots_with_ai(user_message, slots, limit=limit)
    if ai_slots:
        return ai_slots

    preference = parse_slot_preference(user_message)
    if not has_meaningful_slot_preference(preference):
        return []

    scored = [
        (score_slot_against_preference(slot, preference), slot)
        for slot in slots
    ]
    scored.sort(key=lambda item: item[0])
    return [slot for _, slot in scored[:limit]]


def suggest_slots_with_ai(
    user_message: str,
    slots: list[dict],
    limit: int = 5,
) -> list[dict]:
    if not user_message or not slots:
        return []

    prompt = (
        "Ты помогаешь подобрать слот записи в мотосервис.\n"
        "Пользователь уже находится на этапе выбора времени.\n"
        "Нужно понять, описывает ли его сообщение желаемую дату или время, даже если формулировка разговорная.\n"
        "Примеры: 'суббота, вторая половина дня', 'вторник, после обеда', 'на выходные', 'завтра вечером'.\n"
        "Верни JSON c полями:\n"
        "- matched: true/false\n"
        f"- slot_ids: массив максимум из {limit} slot_id в порядке убывания релевантности\n"
        "- clarification: короткая строка, если не удалось распознать запрос\n\n"
        f"Сообщение пользователя: {user_message}\n\n"
        "Доступные слоты:\n"
        + "\n".join(_format_slot_for_ai(slot) for slot in slots)
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Отвечай только JSON без пояснений.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )
        raw_content = response.choices[0].message.content or "{}"
        payload = json.loads(raw_content)
    except Exception as exc:
        logger.warning("OpenAI slot ranking failed, using heuristic ranking: %s", exc)
        return []

    if not isinstance(payload, dict) or not payload.get("matched"):
        return []

    requested_ids = payload.get("slot_ids") or []
    if not isinstance(requested_ids, list):
        return []

    order = {slot_id: idx for idx, slot_id in enumerate(requested_ids[:limit])}
    matched_slots = [slot for slot in slots if slot.get("slot_id") in order]
    matched_slots.sort(key=lambda slot: order.get(slot.get("slot_id"), 10**9))
    return matched_slots[:limit]


def find_matching_slot(user_message: str, offered_slot_ids: list[str] | None = None) -> dict | None:
    slots = get_slot_candidates(offered_slot_ids)
    if not slots:
        return None

    choice_idx = parse_slot_choice(user_message, max_choice=max(len(slots), 5))
    if choice_idx is not None:
        if 0 <= choice_idx < len(slots):
            return slots[choice_idx]
        return slots[-1]

    for slot in slots:
        if _matches_direct_slot_reference(user_message, slot):
            return slot

    return None


def is_slot_change_request(user_message: str) -> bool:
    lowered = (user_message or "").strip().lower()
    return any(pattern in lowered for pattern in CHANGE_SLOT_PATTERNS)


def is_cancel_request(user_message: str) -> bool:
    lowered = (user_message or "").strip().lower()
    return lowered in CANCEL_PATTERNS


def normalize_goal(goal: str, intent: str = "") -> str:
    text = (goal or "").strip().lower()
    normalized_intent = (intent or "").strip().lower()

    if not text:
        return ""

    if normalized_intent == "ecu":
        return "настройка"
    if normalized_intent in {"dyno", "afr"}:
        return "замер"
    if normalized_intent in {"diagnostics", "contacts"}:
        return "консультация"

    consultation_tokens = [
        "консультац", "подобрать", "посовет", "понять", "что делать",
        "разобраться", "подскаж", "помощ", "интересует", "хочу понять",
    ]
    measurement_tokens = [
        "замер", "стенд", "дино", "dyno", "power run", "смесь", "afr",
        "посмотреть смесь", "проверить смесь",
    ]
    tuning_tokens = [
        "настрой", "ecu", "прошив", "flash", "калибров", "карта",
    ]

    if any(token in text for token in consultation_tokens):
        return "консультация"
    if any(token in text for token in tuning_tokens):
        return "настройка"
    if any(token in text for token in measurement_tokens):
        return "замер"

    return goal.strip()

def infer_goal_from_message(message: str, intent: str = "") -> str:
    text = (message or "").strip()
    lowered = text.lower()
    normalized = normalize_goal(text, intent)

    if normalized and normalized != text:
        return text

    service_goal_tokens = [
        "мощност", "отклик", "провал", "тяга", "едет", "поехать",
        "разгон", "ускор", "полка", "смесь", "ровнее", "лучше едет",
        "убрать провалы", "поднять мощность", "улучшить отклик",
        "настроить", "проверить", "посмотреть", "диагност", "консультац",
    ]
    if any(token in lowered for token in service_goal_tokens):
        return text

    if not text:
        return ""

    prompt = (
        "Определи, содержит ли сообщение пользователя уже сформулированную цель обращения "
        "в мотосервис по настройке, диагностике, замеру или консультации.\n"
        "Нужно учитывать и бытовые формулировки вроде: 'хочу поднять мощность', "
        "'хочу убрать провалы', 'нужно улучшить отклик', 'плохо едет снизу'.\n"
        "Верни JSON с полями:\n"
        "- has_goal: true/false\n"
        "- goal: короткая строка с сутью запроса пользователя, если она есть\n\n"
        f"Intent: {intent}\n"
        f"Сообщение: {text}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Отвечай только JSON без пояснений."},
                {"role": "user", "content": prompt},
            ],
        )
        payload = json.loads(response.choices[0].message.content or "{}")
    except Exception as exc:
        logger.warning("OpenAI goal extraction failed, using heuristic only: %s", exc)
        return ""

    if not isinstance(payload, dict) or not payload.get("has_goal"):
        return ""

    goal = (payload.get("goal") or "").strip()
    return goal or text


def is_consultation_request(user_message: str) -> bool:
    lowered = (user_message or "").strip().lower()
    if not lowered:
        return False
    return any(pattern in lowered for pattern in CONSULTATION_REQUEST_PATTERNS)


def build_consultation_goal(message: str, collected_data: dict) -> str:
    raw_message = (message or "").strip()
    previous_goal = (collected_data.get("goal") or "").strip()
    if previous_goal.lower().startswith("консультация по вопросу:"):
        previous_goal = previous_goal.split(":", 1)[1].strip()

    inferred_goal = infer_goal_from_message(raw_message, collected_data.get("intent") or "")
    normalized_inferred = normalize_goal(inferred_goal, collected_data.get("intent") or "")

    if inferred_goal and normalized_inferred != "консультация":
        return inferred_goal

    if previous_goal:
        normalized_previous = normalize_goal(previous_goal, collected_data.get("intent") or "")
        if normalized_previous == "консультация":
            return previous_goal
        return f"консультация по вопросу: {previous_goal}"

    if raw_message and is_consultation_request(raw_message):
        return "консультация"

    return inferred_goal or "консультация"

def build_slot_notes(collected_data: dict, preserve_goal_detail: bool = False) -> str:
    make = (collected_data.get("make") or "").strip()
    model = (collected_data.get("model") or "").strip()
    year = (collected_data.get("year") or "").strip()
    raw_goal = (collected_data.get("goal") or "").strip()
    normalized_goal = normalize_goal(
        raw_goal,
        collected_data.get("intent") or "",
    )
    goal = (
        raw_goal
        if preserve_goal_detail and raw_goal
        else normalized_goal
    )
    contact = (collected_data.get("contact") or "").strip()

    bike_parts = [part for part in [make, model, year] if part]
    notes_parts = []

    if bike_parts:
        notes_parts.append(f"bike={' '.join(bike_parts)}")
    if goal:
        notes_parts.append(f"goal={goal}")
    if contact:
        notes_parts.append(f"contact={contact}")

    return "; ".join(notes_parts)


def create_consultation_request(collected_data: dict, message: str = "") -> dict:
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    existing_slots = _read_all_slots()

    max_slot_number = 0
    slot_width = 4
    for slot in existing_slots:
        slot_id = str(slot.get("slot_id") or "").strip()
        match = re.fullmatch(r"slot_(\d+)", slot_id, re.IGNORECASE)
        if not match:
            continue
        number_text = match.group(1)
        max_slot_number = max(max_slot_number, int(number_text))
        slot_width = max(slot_width, len(number_text))

    next_slot_number = max_slot_number + 1
    slot_id = f"slot_{next_slot_number:0{slot_width}d}"

    callback_data = {
        **collected_data,
        "goal": build_consultation_goal(message, collected_data),
    }
    notes = build_slot_notes(callback_data, preserve_goal_detail=True)

    try:
        append_result = append_slot(
            [
                slot_id,
                now.strftime("%Y_%m_%d"),
                now.strftime("%H:%M"),
                "",
                "need info",
                notes,
            ],
            highlight_yellow=True,
        )
        return {
            "ok": True,
            "slot_id": slot_id,
            "row_number": append_result.get("row_number"),
            "notes": notes,
            "selected_slot": "TBD/",
            "goal": callback_data.get("goal"),
        }
    except Exception as exc:
        logger.warning("Google Sheets consultation append failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def book_slot(slot: dict, collected_data: dict | None = None) -> dict:
    row_number = slot.get("_row_number")
    if not row_number:
        return {"ok": False, "error": "row number not found"}

    notes = build_slot_notes(collected_data or {})

    try:
        update_result = update_slot_status(row_number, "booked", notes)
        return {"ok": True, "update_result": update_result, "notes": notes}
    except Exception as exc:
        logger.warning("Google Sheets slot booking failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def release_slot(slot_id: str | None) -> dict:
    slot = get_slot_by_id(slot_id)
    if not slot:
        return {"ok": False, "error": "slot not found"}

    row_number = slot.get("_row_number")
    if not row_number:
        return {"ok": False, "error": "row number not found"}

    try:
        update_result = update_slot_status(row_number, "free", "")
        return {"ok": True, "update_result": update_result}
    except Exception as exc:
        logger.warning("Google Sheets slot release failed: %s", exc)
        return {"ok": False, "error": str(exc)}
