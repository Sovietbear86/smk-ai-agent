import logging
import re

from app.integrations.google_sheets import read_slots, update_slot_status

logger = logging.getLogger(__name__)


def get_free_slots(limit: int = 3):
    try:
        slots = read_slots()
    except Exception as exc:
        logger.warning("Google Sheets slots read failed, continuing without slots: %s", exc)
        return []

    free_slots = [slot for slot in slots if slot.get("status", "").lower() == "free"]
    return free_slots[:limit]


def parse_slot_choice(user_message: str) -> int | None:
    text = user_message.lower().strip()

    if any(x in text for x in ["любой", "без разницы", "ближайший", "самый ранний", "любой вариант"]):
        return 0

    first_patterns = [
        "1", "1.", "1)", "1-й", "1й",
        "перв", "один", "одну", "первый", "первое", "первому", "первый вариант", "первое окно",
    ]
    second_patterns = [
        "2", "2.", "2)", "2-й", "2й",
        "втор", "два", "второй", "второе", "второму", "второй вариант", "второе окно",
    ]
    third_patterns = [
        "3", "3.", "3)", "3-й", "3й",
        "трет", "три", "третий", "третье", "третьему", "третий вариант", "третье окно",
    ]

    def contains_pattern(patterns: list[str]) -> bool:
        for pattern in patterns:
            if pattern in {"1", "2", "3"}:
                if re.search(rf"\b{re.escape(pattern)}\b", text):
                    return True
            elif pattern in text:
                return True
        return False

    if contains_pattern(first_patterns):
        return 0
    if contains_pattern(second_patterns):
        return 1
    if contains_pattern(third_patterns):
        return 2

    return None


def find_matching_slot(user_message: str):
    text = user_message.lower().strip()
    free_slots = get_free_slots(limit=20)

    if not free_slots:
        return None

    choice_idx = parse_slot_choice(user_message)
    if choice_idx is not None:
        if 0 <= choice_idx < len(free_slots):
            return free_slots[choice_idx]
        return free_slots[-1]

    for slot in free_slots:
        candidate = f"{slot.get('date')} {slot.get('start_time')}-{slot.get('end_time')}".lower()
        candidate_alt = f"{slot.get('date')} {slot.get('start_time')} - {slot.get('end_time')}".lower()

        if candidate in text or text in candidate:
            return slot
        if candidate_alt in text or text in candidate_alt:
            return slot

    for slot in free_slots:
        start_time = str(slot.get("start_time", "")).lower()
        end_time = str(slot.get("end_time", "")).lower()

        if start_time and start_time in text:
            return slot
        if end_time and end_time in text:
            return slot

    return None


def normalize_goal(goal: str, intent: str = "") -> str:
    text = (goal or "").strip().lower()
    normalized_intent = (intent or "").strip().lower()

    if normalized_intent == "ecu":
        return "настройка"
    if normalized_intent in {"dyno", "afr"}:
        return "замер"
    if normalized_intent in {"diagnostics", "contacts"}:
        return "консультация"

    if not text:
        return "консультация" if normalized_intent == "other" else ""

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

    if any(token in text for token in tuning_tokens):
        return "настройка"
    if any(token in text for token in measurement_tokens):
        return "замер"
    if any(token in text for token in consultation_tokens):
        return "консультация"

    return goal.strip()


def build_slot_notes(collected_data: dict) -> str:
    make = (collected_data.get("make") or "").strip()
    model = (collected_data.get("model") or "").strip()
    year = (collected_data.get("year") or "").strip()
    goal = normalize_goal(
        collected_data.get("goal") or "",
        collected_data.get("intent") or "",
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


def book_slot(slot: dict, collected_data: dict | None = None):
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
