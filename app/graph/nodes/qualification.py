from app.services.availability_service import book_slot, build_slot_notes, find_matching_slot, get_free_slots


def qualification(state):
    intent = state.get("intent", "other")
    entities = state.get("entities", {})
    collected = state.get("collected_data", {}).copy()
    test_mode = state.get("test_mode", False)

    for key, value in entities.items():
        collected[key] = value
    if intent:
        collected["intent"] = intent

    message = state.get("user_message", "")
    lower_message = message.lower()
    booking_stage = state.get("booking_stage", "not_started")

    if any(x in lower_message for x in ["диагност", "afr", "настрой", "замер"]):
        collected["goal"] = state.get("user_message")

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
                "answer": "Что именно хотите сделать: замер, диагностику или настройку?",
            }

        if not collected.get("contact"):
            return {
                "collected_data": collected,
                "booking_stage": "need_contact",
                "answer": "Оставьте, пожалуйста, удобный контакт: телефон, Telegram или WhatsApp.",
            }

        slots = get_free_slots()
        if slots:
            slots_text = "\n".join(
                [f"1) {slots[0]['date']} {slots[0]['start_time']}-{slots[0]['end_time']}"]
                + ([f"2) {slots[1]['date']} {slots[1]['start_time']}-{slots[1]['end_time']}"] if len(slots) > 1 else [])
                + ([f"3) {slots[2]['date']} {slots[2]['start_time']}-{slots[2]['end_time']}"] if len(slots) > 2 else [])
            )
            return {
                "collected_data": collected,
                "booking_stage": "offer_slots",
                "answer": (
                    f"Спасибо. Вот ближайшие свободные окна:\n\n"
                    f"{slots_text}\n\n"
                    f"Напишите, какой вариант подходит: 1, 2, 3 или вставьте дату и время текстом."
                ),
            }

        return {
            "collected_data": collected,
            "booking_stage": "ready",
            "answer": "Спасибо. Данные для заявки собраны. Свободных слотов сейчас не найдено, но заявку сохраняю.",
        }

    if booking_stage == "need_bike" and collected.get("make"):
        return {
            "collected_data": collected,
            "booking_stage": "need_goal",
            "answer": "Понял. Что именно хотите сделать: замер, диагностику или настройку?",
        }

    if booking_stage == "need_goal" and collected.get("goal"):
        return {
            "collected_data": collected,
            "booking_stage": "need_contact",
            "answer": "Хорошо. Оставьте, пожалуйста, удобный контакт: телефон, Telegram или WhatsApp.",
        }

    if booking_stage == "need_contact" and collected.get("contact"):
        slots = get_free_slots()
        if slots:
            lines = []
            for i, slot in enumerate(slots[:3], start=1):
                lines.append(f"{i}) {slot['date']} {slot['start_time']}-{slot['end_time']}")
            slots_text = "\n".join(lines)

            return {
                "collected_data": collected,
                "booking_stage": "offer_slots",
                "answer": (
                    f"Спасибо. Вот ближайшие свободные окна:\n\n"
                    f"{slots_text}\n\n"
                    f"Напишите, какой вариант подходит: 1, 2, 3 или вставьте дату и время текстом."
                ),
            }

        return {
            "collected_data": collected,
            "booking_stage": "ready",
            "answer": "Спасибо. Данные для заявки собраны. Свободных слотов сейчас не найдено, но заявку сохраняю.",
        }

    if booking_stage == "offer_slots":
        matched_slot = find_matching_slot(message)

        if not matched_slot:
            return {
                "collected_data": collected,
                "booking_stage": "offer_slots",
                "answer": "Не смог точно определить выбранный слот. Напишите 1, 2, 3 или дату и время в формате 2026-04-05 11:00-13:00.",
            }

        if not test_mode:
            book_result = book_slot(matched_slot, collected)
            if not book_result.get("ok"):
                return {
                    "collected_data": collected,
                    "booking_stage": "offer_slots",
                    "answer": "Не удалось зафиксировать слот. Попробуйте выбрать другой вариант.",
                }

        collected["selected_slot"] = f"{matched_slot.get('date')} {matched_slot.get('start_time')}-{matched_slot.get('end_time')}"
        collected["booked_slot_id"] = matched_slot.get("slot_id")
        collected["notes"] = (
            book_result.get("notes")
            if not test_mode
            else build_slot_notes(collected)
        )
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

    return {
        "collected_data": collected,
        "booking_stage": booking_stage,
        "answer": "",
    }
