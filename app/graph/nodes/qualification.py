from app.services.availability_service import (
    book_slot,
    build_slot_notes,
    find_matching_slot,
    format_slot,
    get_free_slots,
    infer_goal_from_message,
    is_cancel_request,
    is_slot_change_request,
    might_be_slot_preference_message,
    release_slot,
    suggest_slots_for_preference,
)


def _looks_like_bike_description(message: str, entities: dict) -> bool:
    lower_message = (message or "").lower()
    tokens = [token for token in lower_message.replace(",", " ").split() if token]

    if entities.get("make") or entities.get("model"):
        return True

    if entities.get("year") and tokens:
        return True

    if any(char.isdigit() for char in lower_message):
        modelish_tokens = [
            token
            for token in tokens
            if any(char.isdigit() for char in token)
            and len(token) >= 3
            and "@" not in token
        ]
        if modelish_tokens:
            return True

    bike_words = {
        "мото", "мотоцикл", "байк", "honda", "yamaha", "suzuki", "kawasaki",
        "bmw", "ducati", "ktm", "triumph", "aprilia", "harley", "indian",
        "хонда", "ямаха", "сузуки", "кавасаки", "бмв", "дукати", "ктм",
        "триумф", "априлия", "харлей", "индиан", "вуфер", "гусь", "гантеля",
        "сутенер", "голда", "версус", "кавас", "фужер", "мультистрада",
        "мультистрадания",
    }
    return any(word in lower_message for word in bike_words)


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


def _build_post_booking_closure(collected: dict) -> dict:
    slot = collected.get("selected_slot")
    if slot:
        answer = (
            f"Пожалуйста. Запись на {slot} уже сохранена. "
            "Если захотите изменить время или оформить ещё одну запись, просто напишите об этом."
        )
    else:
        answer = (
            "Пожалуйста. Запись уже сохранена. "
            "Если захотите изменить время или оформить ещё одну запись, просто напишите об этом."
        )

    return {
        "collected_data": collected,
        "booking_stage": "ready",
        "answer": answer,
    }


def _is_new_booking_request(message: str, intent: str) -> bool:
    lower_message = (message or "").lower()
    booking_like_intent = intent in {"booking", "ecu", "dyno", "afr", "diagnostics"}
    if not booking_like_intent:
        return False

    phrases = (
        "еще",
        "ещё",
        "повторно",
        "снова запис",
        "новая запись",
        "еще один слот",
        "ещё один слот",
        "другой мотоцикл",
        "второй мотоцикл",
        "еще один мотоцикл",
        "ещё один мотоцикл",
    )
    return any(phrase in lower_message for phrase in phrases)


def _mentions_another_bike(message: str) -> bool:
    lower_message = (message or "").lower()
    phrases = (
        "другой мотоцикл",
        "второй мотоцикл",
        "еще один мотоцикл",
        "ещё один мотоцикл",
        "другой байк",
        "второй байк",
    )
    return any(phrase in lower_message for phrase in phrases)


def _restart_booking_after_ready(
    previous_collected: dict,
    current_collected: dict,
    message: str,
    intent: str,
) -> dict:
    next_collected = {
        "contact": previous_collected.get("contact"),
        "contact_type": previous_collected.get("contact_type"),
        "intent": intent,
    }

    if not _mentions_another_bike(message):
        for key in ("make", "model", "year", "goal"):
            if previous_collected.get(key):
                next_collected[key] = previous_collected[key]

    for key in ("make", "model", "year", "goal", "contact", "contact_type", "preferred_slot_request"):
        if current_collected.get(key):
            next_collected[key] = current_collected[key]

    if next_collected.get("make") and next_collected.get("goal"):
        if next_collected.get("contact"):
            preferred_slot_request = next_collected.get("preferred_slot_request")
            slots = (
                suggest_slots_for_preference(preferred_slot_request, limit=5)
                if preferred_slot_request
                else []
            ) or get_free_slots(limit=5)
            if slots:
                intro = (
                    "Понял. Оформляем ещё одну запись. Вот ближайшие подходящие окна:"
                    if preferred_slot_request
                    else "Понял. Оформляем ещё одну запись. Вот ближайшие свободные окна:"
                )
                return _build_offer_response(next_collected, slots, intro)

            return {
                "collected_data": next_collected,
                "booking_stage": "ready",
                "answer": "Понял. Начинаю ещё одну запись с теми же данными, но свободных слотов сейчас не вижу.",
            }

        return {
            "collected_data": next_collected,
            "booking_stage": "need_contact",
            "answer": "Понял. Оформляем ещё одну запись. Оставьте, пожалуйста, удобный контакт: телефон, Telegram или WhatsApp.",
        }

    if next_collected.get("make"):
        return {
            "collected_data": next_collected,
            "booking_stage": "need_goal",
            "answer": "Понял. Оформляем ещё одну запись. Что именно хотите сделать: настройку, замер или консультацию?",
        }

    return {
        "collected_data": next_collected,
        "booking_stage": "need_bike",
        "answer": "Понял. Оформляем ещё одну запись. Какой у вас мотоцикл: марка, модель и год?",
    }


def qualification(state):
    intent = state.get("intent", "other")
    entities = state.get("entities", {})
    previous_collected = state.get("collected_data", {}).copy()
    collected = previous_collected.copy()
    test_mode = state.get("test_mode", False)
    lead_saved = bool(state.get("lead_saved", False))

    for key, value in entities.items():
        collected[key] = value
    if intent:
        collected["intent"] = intent

    message = state.get("user_message", "").strip()
    lower_message = message.lower()
    booking_stage = state.get("booking_stage", "not_started")
    booking_intents = {"booking", "ecu", "dyno", "afr", "diagnostics", "contacts"}

    inferred_goal = infer_goal_from_message(message, intent)
    if inferred_goal:
        collected["goal"] = inferred_goal
    if might_be_slot_preference_message(message):
        collected["preferred_slot_request"] = message

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

    if booking_stage == "ready" and _is_new_booking_request(message, intent):
        return _restart_booking_after_ready(previous_collected, collected, message, intent)

    if booking_stage == "ready":
        return _build_post_booking_closure(collected)

    has_booking_context = bool(
        collected.get("make") and collected.get("goal") and collected.get("contact")
    )

    if has_booking_context and might_be_slot_preference_message(message):
        offered_slot_ids = collected.get("offered_slot_ids") or []

        if booking_stage != "offer_slots":
            suggested_slots = suggest_slots_for_preference(
                message,
                limit=5,
                offered_slot_ids=offered_slot_ids,
            ) or get_free_slots(limit=5)
            return _build_offer_response(
                collected,
                suggested_slots,
                "Понял. Продолжаем подбор времени без повторного заполнения заявки.",
            )

    if booking_stage == "need_bike" and collected.get("make"):
        if collected.get("goal"):
            return {
                "collected_data": collected,
                "booking_stage": "need_contact",
                "answer": "Хорошо. Оставьте, пожалуйста, удобный контакт: телефон, Telegram или WhatsApp.",
            }
        return {
            "collected_data": collected,
            "booking_stage": "need_goal",
            "answer": "Понял. Что именно хотите сделать: настройку, замер или консультацию?",
        }

    if booking_stage == "need_bike" and _looks_like_bike_description(message, entities):
        return {
            "collected_data": collected,
            "booking_stage": "need_bike",
            "answer": (
                "Похоже, речь о модели мотоцикла, но я не смог точно распознать марку. "
                "Напишите, пожалуйста, марку и модель чуть подробнее, например: "
                "Honda VFR1200X 2016 или Yamaha FJR1300 2014."
            ),
        }

    if booking_stage == "need_goal" and collected.get("goal"):
        return {
            "collected_data": collected,
            "booking_stage": "need_contact",
            "answer": "Хорошо. Оставьте, пожалуйста, удобный контакт: телефон, Telegram или WhatsApp.",
        }

    if booking_stage == "need_contact" and collected.get("contact"):
        preferred_slot_request = collected.get("preferred_slot_request")
        slots = (
            suggest_slots_for_preference(preferred_slot_request, limit=5)
            if preferred_slot_request
            else []
        ) or get_free_slots(limit=5)
        if slots:
            intro = (
                "Под ваш запрос ближе всего подходят такие свободные окна:"
                if preferred_slot_request
                else None
            )
            return _build_offer_response(collected, slots, intro)

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

    should_enter_booking_funnel = intent in booking_intents or bool(collected.get("goal"))

    if should_enter_booking_funnel:
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

        preferred_slot_request = collected.get("preferred_slot_request")
        slots = (
            suggest_slots_for_preference(preferred_slot_request, limit=5)
            if preferred_slot_request
            else []
        ) or get_free_slots(limit=5)
        if slots:
            intro = (
                "Под ваш запрос ближе всего подходят такие свободные окна:"
                if preferred_slot_request
                else None
            )
            return _build_offer_response(collected, slots, intro)

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
