from typing import Any


def enrich_result_with_ui(result: dict[str, Any]) -> dict[str, Any]:
    booking_stage = result.get("booking_stage", "not_started")
    collected_data = result.get("collected_data", {}) or {}
    available_slots = result.get("available_slots", []) or []

    quick_replies: list[dict[str, str]] = []

    bike_brand = (collected_data.get("bike_brand") or "").strip().lower()
    goal = (collected_data.get("goal") or "").strip().lower()

    if booking_stage == "not_started":
        quick_replies = [
            {"label": "Настройка ECU", "value": "Интересует настройка ECU"},
            {"label": "Диностенд", "value": "Хочу записаться на диностенд"},
            {"label": "Консультация", "value": "Нужна консультация по тюнингу"},
        ]

    elif booking_stage in {"qualification", "collect_goal"} and not goal:
        quick_replies = [
            {"label": "Прошивка ECU", "value": "Нужна прошивка ECU"},
            {"label": "Замер на стенде", "value": "Нужен замер на диностенде"},
            {"label": "Подобрать тюнинг", "value": "Помогите подобрать тюнинг"},
        ]

    elif booking_stage in {"collect_bike", "collect_bike_info"} and not bike_brand:
        quick_replies = [
            {"label": "Honda", "value": "Honda"},
            {"label": "Yamaha", "value": "Yamaha"},
            {"label": "BMW", "value": "BMW"},
            {"label": "Kawasaki", "value": "Kawasaki"},
            {"label": "Suzuki", "value": "Suzuki"},
            {"label": "Ducati", "value": "Ducati"},
        ]

    elif booking_stage == "choose_slot" and available_slots:
        # quick replies не нужны, потому что слоты отрисуются отдельно
        quick_replies = []

    elif booking_stage == "ready":
        quick_replies = [
            {"label": "Изменить слот", "value": "Хочу выбрать другой слот"},
        ]

    return {
        **result,
        "quick_replies": quick_replies,
        "available_slots": available_slots,
    }
