from app.services.availability_service import (
    book_slot,
    build_slot_notes,
    find_matching_slot,
    format_slot,
    get_free_slots,
    is_cancel_request,
    is_slot_change_request,
    release_slot,
    suggest_slots_for_preference,
)


def _build_offer_response(collected: dict, slots: list[dict], intro: str | None = None) -> dict:
    slot_labels = [format_slot(slot) for slot in slots]
    lines = [f"{idx}) {label}" for idx, label in enumerate(slot_labels, start=1)]
    prefix = intro or "Спасибо. Вот ближайшие свободные окна:"

    return {
        "collected_data": {
            **collected,
            "offered_slot_ids": [slot.get("slot_id") for slot in slots],
        },
        "booking_stage": "offer_slots",
        "available_slots": slot_labels,
        "answer": (
            f"{prefix}\n\n"
            f"{chr(10).join(lines)}\n\n"
            "Можно выбрать номер, написать дату и время своими словами "
            "или попросить другой диапазон, например: завтра утром, в понедельник, на выходные."
        ),
    }


def qualification(state):
    intent = state.get("intent", "other")
    entities = state.get("entities", {})
    collected = state.get("collected_data", {}).copy()
    test_mode = state.get("test_mode", False)
    lead_saved = bool(state.get("lead_saved", False))

    for key, value in entities.items():
        collected[key] = value
    if intent:
        collected["intent"] = intent

    message = state.get("user_message", "").strip()
    lower_message = message.lower()
    booking_stage = state.get("booking_stage", "not_started")

    if any(token in lower_message for token in ["диагност", "afr", "настрой", "замер", "консультац", "ecu"]):
        collected["goal"] = message

    if is_cancel_request(message):
        booked_slot_id = collected.get("booked_slot_id")
        if booked_slot_id and lead_saved and not test_mode:
            release_slot(booked_slot_id)
        return {
            "collected_data": {},
            "booking_stage": "cancelled",
            "answer": "Понял. Тогда отменяем запись. Будем рады видеть вас в другой раз.",
        }

    if booking_stage == "ready" and is_slot_change_request(message):
        slots = get_free_slots(limit=5)
        if not slots:
            return {
                "collected_data": collected,
                "booking_stage": "offer_slots",
                "answer": "Свободных слотов прямо сейчас не вижу. Можете написать желаемую дату и время, а мы подберем ближайший вариант вручную.",
            }
        return _build_offer_response(collected, slots, "Понял. Давайте подберем другой слот без повторного заполнения заявки.")

    if booking_stage == "need_bike" and collected.get("make"):
        return {
            "collected_data": collected,
            "booking_stage": "need_goal",
            "answer": "Понял. Что именно хотите сделать: настройку, замер или консультацию?",
        }

    if booking_stage == "need_goal" and collected.get("goal"):
        return {
            "collected_data": collected,
            "booking_stage": "need_contact",
            "answer": "Хорошо. Оставьте, пожалуйста, удобный контакт: телефон, Telegram или WhatsApp.",
        }

    if booking_stage == "need_contact" and collected.get("contact"):
        slots = get_free_slots(limit=5)
        if slots:
            return _build_offer_response(collected, slots)

        return {
            "collected_data": collected,
            "booking_stage": "ready",
            "answer": "Спасибо. Данные для заявки собраны. Свободных слотов сейчас не найдено, но заявку сохраняю.",
        }

    if booking_stage == "offer_slots":
        offered_slot_ids = collected.get("offered_slot_ids") or []
        matched_slot = find_matching_slot(message, offered_slot_ids=offered_slot_ids)

        if matched_slot:
            previous_slot_id = collected.get("booked_slot_id")
            if previous_slot_id and previous_slot_id != matched_slot.get("slot_id") and lead_saved and not test_mode:
                release_result = release_slot(previous_slot_id)
                if not release_result.get("ok"):
                    return {
                        "collected_data": collected,
                        "booking_stage": "offer_slots",
                        "answer": "Не удалось освободить предыдущий слот. Попробуйте еще раз чуть позже.",
                    }

            if not test_mode:
                book_result = book_slot(matched_slot, collected)
                if not book_result.get("ok"):
                    return {
                        "collected_data": collected,
                        "booking_stage": "offer_slots",
                        "answer": "Не удалось зафиксировать слот. Попробуйте выбрать другой вариант.",
                    }

            collected["selected_slot"] = format_slot(matched_slot)
            collected["booked_slot_id"] = matched_slot.get("slot_id")
            collected["notes"] = (
                book_result.get("notes")
                if not test_mode
                else build_slot_notes(collected)
            )
            collected.pop("offered_slot_ids", None)

            if test_mode:
                collected["booked_slot_id"] = f"test:{matched_slot.get('slot_id')}"

            return {
                "collected_data": collected,
                "booking_stage": "ready",
                "answer": (
                    "Тестовый режим: подобрал слот, но не бронирую его в Google Sheets."
                    if test_mode
                    else "Отлично, слот зафиксировал. Сохраняю заявку."
                ),
            }

        suggested_slots = suggest_slots_for_preference(
            message,
            limit=5,
            offered_slot_ids=offered_slot_ids,
        )
        if suggested_slots:
            return _build_offer_response(
                collected,
                suggested_slots,
                "Под ваш запрос ближе всего подходят такие свободные окна:",
            )

        return {
            "collected_data": collected,
            "booking_stage": "offer_slots",
            "answer": (
                "Не смог подобрать слот по этому описанию. "
                "Можно написать проще: завтра, в понедельник вечером, первого марта, на выходные."
            ),
        }

    if intent == "booking":
        if not collected.get("make"):
            return {
                "collected_data": collected,
                "booking_stage": "need_bike",
                "answer": "Отлично. Какой у вас мотоцикл: марка, модель и год?",
            }

        if not collected.get("goal"):
            return {
                "collected_data": collected,
                "booking_stage": "need_goal",
                "answer": "Что именно хотите сделать: настройку, замер или консультацию?",
            }

        if not collected.get("contact"):
            return {
                "collected_data": collected,
                "booking_stage": "need_contact",
                "answer": "Оставьте, пожалуйста, удобный контакт: телефон, Telegram или WhatsApp.",
            }

        slots = get_free_slots(limit=5)
        if slots:
            return _build_offer_response(collected, slots)

        return {
            "collected_data": collected,
            "booking_stage": "ready",
            "answer": "Спасибо. Данные для заявки собраны. Свободных слотов сейчас не найдено, но заявку сохраняю.",
        }

    return {
        "collected_data": collected,
        "booking_stage": booking_stage,
        "answer": "",
    }
