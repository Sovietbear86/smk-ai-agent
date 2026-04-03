import re
from app.integrations.google_sheets import read_slots, update_slot_status


def get_free_slots(limit: int = 3):
    slots = read_slots()
    free_slots = [slot for slot in slots if slot.get("status", "").lower() == "free"]
    return free_slots[:limit]


def parse_slot_choice(user_message: str) -> int | None:
    text = user_message.lower().strip()

    # "любой", "без разницы", "ближайший" -> первый слот
    if any(x in text for x in ["любой", "без разницы", "ближайший", "самый ранний", "любой вариант"]):
        return 0

    first_patterns = [
        "1", "1.", "1)", "1-й", "1й",
        "перв", "один", "одну", "первый", "первое", "первому", "первый вариант", "первое окно"
    ]
    second_patterns = [
        "2", "2.", "2)", "2-й", "2й",
        "втор", "два", "второй", "второе", "второму", "второй вариант", "второе окно"
    ]
    third_patterns = [
        "3", "3.", "3)", "3-й", "3й",
        "трет", "три", "третий", "третье", "третьему", "третий вариант", "третье окно"
    ]

    def contains_pattern(patterns: list[str]) -> bool:
        for p in patterns:
            if p in {"1", "2", "3"}:
                if re.search(rf"\b{re.escape(p)}\b", text):
                    return True
            else:
                if p in text:
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

    # 1. Сначала пытаемся понять номер варианта
    choice_idx = parse_slot_choice(user_message)
    if choice_idx is not None:
        if 0 <= choice_idx < len(free_slots):
            return free_slots[choice_idx]
        return free_slots[-1]  # мягкий fallback, если пользователь выбрал "3", а слотов только 2

    # 2. Потом пытаемся матчить по дате и времени
    for slot in free_slots:
        candidate = f"{slot.get('date')} {slot.get('start_time')}-{slot.get('end_time')}".lower()
        candidate_alt = f"{slot.get('date')} {slot.get('start_time')} - {slot.get('end_time')}".lower()

        if candidate in text or text in candidate:
            return slot
        if candidate_alt in text or text in candidate_alt:
            return slot

    # 3. Отдельный случай: пользователь пишет только время, например "на 11:00"
    for slot in free_slots:
        start_time = str(slot.get("start_time", "")).lower()
        end_time = str(slot.get("end_time", "")).lower()

        if start_time and start_time in text:
            return slot
        if end_time and end_time in text:
            return slot

    return None


def book_slot(slot: dict):
    row_number = slot.get("_row_number")
    if not row_number:
        return {"ok": False, "error": "row number not found"}

    update_result = update_slot_status(row_number, "booked")
    return {"ok": True, "update_result": update_result}