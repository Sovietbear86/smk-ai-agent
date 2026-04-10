import re

from app.services.availability_service import (
    book_slot,
    build_consultation_goal,
    build_slot_notes,
    create_consultation_request,
    find_matching_slot,
    format_slot,
    get_free_slots,
    infer_goal_from_message,
    is_cancel_request,
    is_consultation_request,
    is_slot_change_request,
    might_be_slot_preference_message,
    normalize_goal,
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


def _looks_like_contact_message(message: str, entities: dict) -> bool:
    if entities.get("contact"):
        return True

    lowered = (message or "").strip().lower()
    if not lowered:
        return False

    if "telegram" in lowered or "whatsapp" in lowered:
        return True

    if "@" in lowered:
        return True

    digits_only = "".join(char for char in lowered if char.isdigit())
    return len(digits_only) >= 10


def _contains_service_goal_signal(message: str, intent: str = "") -> bool:
    lowered = (message or "").strip().lower()

    service_tokens = (
        "настрой", "ecu", "прошив", "flash", "калибров", "карта",
        "замер", "стенд", "дино", "dyno", "afr", "смесь",
        "консультац", "подобрать", "посовет", "понять", "что делать",
        "диагност", "мощност", "отклик", "провал", "тяга", "разгон",
        "ускор", "убрать провалы", "поднять мощность", "улучшить отклик",
    )
    return any(token in lowered for token in service_tokens)


def _should_update_goal(
    booking_stage: str,
    message: str,
    entities: dict,
    intent: str = "",
) -> bool:
    if booking_stage in {"offer_slots", "ready", "cancelled"}:
        return False

    if _looks_like_contact_message(message, entities):
        return False

    has_service_signal = _contains_service_goal_signal(message, intent)
    looks_like_bike = _looks_like_bike_description(message, entities)

    if looks_like_bike and not has_service_signal:
        return False

    if might_be_slot_preference_message(message) and not has_service_signal:
        return False

    return True


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


def _is_offer_slots_hesitation(message: str) -> bool:
    lowered = (message or "").strip().lower()
    hesitation_phrases = (
        "не готов",
        "не готов к записи",
        "пока не готов",
        "позже",
        "в другой раз",
        "в другое время",
        "не сейчас",
        "сначала нужно получить ответ",
        "сначала хочу получить ответ",
        "нужна консультация",
        "перезвоните",
        "перезвони",
        "свяжитесь",
    )
    return any(phrase in lowered for phrase in hesitation_phrases)


def _is_yes_like(message: str) -> bool:
    lowered = (message or "").strip().lower()
    return lowered in {"да", "ага", "угу", "нужна", "нужна консультация", "хочу консультацию", "перезвоните"}


def _is_no_like(message: str) -> bool:
    lowered = (message or "").strip().lower()
    no_phrases = (
        "нет",
        "не надо",
        "не нужна",
        "не нужна консультация",
        "не готов",
        "пока не готов",
        "в другой раз",
        "в другое время",
        "не сейчас",
    )
    return lowered in no_phrases or any(phrase == lowered for phrase in no_phrases)


def _should_offer_consultation_callback(booking_stage: str, message: str) -> bool:
    if booking_stage in {"offer_slots", "ready", "cancelled"}:
        return False
    return is_consultation_request(message)


def _is_consultation_goal(collected: dict) -> bool:
    if collected.get("pending_callback_request") or collected.get("callback_requested"):
        return True
    goal = (collected.get("goal") or "").strip()
    if not goal:
        return False
    intent = collected.get("intent") or ""
    return is_consultation_request(goal) or normalize_goal(goal, intent) == "консультация"


def _finalize_consultation_request(collected: dict, message: str, test_mode: bool) -> dict:
    existing_goal = (collected.get("goal") or "").strip()
    source_message = "" if _looks_like_contact_message(message, {"contact": collected.get("contact")}) else message
    updated = {
        **collected,
        "goal": existing_goal or build_consultation_goal(source_message, collected),
    }

    if test_mode:
        updated["selected_slot"] = "TBD/"
        updated["booked_slot_id"] = "test:consultation"
        updated["notes"] = build_slot_notes(updated, preserve_goal_detail=True)
        updated["callback_requested"] = True
        updated.pop("pending_callback_request", None)
        updated["request_status"] = "need info"
        return {
            "collected_data": updated,
            "booking_stage": "ready",
            "answer": "Тестовый режим: консультационный запрос собран. Мы бы связались с клиентом в ближайшее время.",
        }

    result = create_consultation_request(updated, message)
    if not result.get("ok"):
        return {
            "collected_data": updated,
            "booking_stage": "need_contact",
            "answer": "Не удалось сохранить заявку на консультацию. Оставьте контакт ещё раз или попробуйте чуть позже.",
        }

    updated["goal"] = result.get("goal", updated.get("goal"))
    updated["selected_slot"] = result.get("selected_slot", "TBD/")
    updated["booked_slot_id"] = result.get("slot_id")
    updated["notes"] = result.get("notes")
    updated["callback_requested"] = True
    updated.pop("pending_callback_request", None)
    updated["request_status"] = "need info"
    return {
        "collected_data": updated,
        "booking_stage": "ready",
        "answer": "Спасибо. Мы свяжемся с вами в ближайшее время.",
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


def _mentions_other_person(message: str) -> bool:
    lower_message = (message or "").lower()
    if "для другого человека" in lower_message:
        return True

    patterns = (
        r"\bдруг\b",
        r"\bдруга\b",
        r"\bдругу\b",
        r"\bродственник\b",
        r"\bродственника\b",
        r"\bжена\b",
        r"\bмуж\b",
        r"\bбрат\b",
        r"\bсестра\b",
        r"\bотец\b",
        r"\bпапа\b",
        r"\bмама\b",
        r"\bсын\b",
        r"\bдочь\b",
    )
    return any(re.search(pattern, lower_message) for pattern in patterns)


def _mentions_new_work_same_bike(message: str) -> bool:
    lower_message = (message or "").lower()
    phrases = (
        "другая работа",
        "другой вид работ",
        "другой тип работ",
        "еще одна работа",
        "ещё одна работа",
        "другая услуга",
        "еще одна услуга",
        "ещё одна услуга",
        "на этот же мотоцикл",
        "для этого же мотоцикла",
    )
    return any(phrase in lower_message for phrase in phrases)


def _mentions_additional_slot_same_work(message: str) -> bool:
    lower_message = (message or "").lower()
    phrases = (
        "еще один слот",
        "ещё один слот",
        "еще слот",
        "ещё слот",
        "дополнительный слот",
        "для этого же мотоцикла",
    )
    return any(phrase in lower_message for phrase in phrases)


def _mentions_same_work(message: str) -> bool:
    lower_message = (message or "").lower()
    phrases = (
        "тот же тип работ",
        "тот же тип работы",
        "та же работа",
        "та же услуга",
        "то же самое",
        "то же",
        "тоже",
        "так же",
        "такой же",
        "аналогично",
        "тот же запрос",
        "тот же вид работ",
    )
    return any(phrase in lower_message for phrase in phrases)


def _mentions_different_work(message: str) -> bool:
    lower_message = (message or "").lower()
    return _mentions_new_work_same_bike(message) or any(
        phrase in lower_message
        for phrase in (
            "другой тип работ",
            "другой тип работы",
            "другой вид работ",
            "другая работа",
            "другая услуга",
        )
    )


def _build_same_bike_work_clarification(collected: dict) -> dict:
    return {
        "collected_data": {
            **collected,
            "pending_additional_booking": "same_bike_unspecified_work",
        },
        "booking_stage": "ready",
        "answer": (
            "Понял. Для этого же мотоцикла нужна запись на тот же тип работ или на другой? "
            "Если тот же, сразу подберу ещё один слот. Если другой, спрошу новую цель."
        ),
    }


def _restart_booking_after_ready(
    previous_collected: dict,
    current_collected: dict,
    message: str,
    intent: str,
) -> dict:
    another_bike = _mentions_another_bike(message)
    other_person = _mentions_other_person(message)
    new_work_same_bike = _mentions_new_work_same_bike(message)
    additional_slot_same_work = _mentions_additional_slot_same_work(message)
    same_work = _mentions_same_work(message)
    different_work = _mentions_different_work(message)

    pending_mode = previous_collected.get("pending_additional_booking")
    if pending_mode == "same_bike_unspecified_work":
        if different_work:
            new_work_same_bike = True
            additional_slot_same_work = False
        elif same_work or not different_work:
            additional_slot_same_work = True
            new_work_same_bike = False

    if additional_slot_same_work:
        new_work_same_bike = False

    if another_bike or other_person:
        next_collected = {
            "intent": intent,
        }
    else:
        next_collected = {
            "intent": intent,
        }

    if not other_person and not another_bike:
        next_collected["contact"] = previous_collected.get("contact")
        next_collected["contact_type"] = previous_collected.get("contact_type")

    if not another_bike:
        for key in ("make", "model", "year", "goal"):
            if previous_collected.get(key):
                next_collected[key] = previous_collected[key]

    for key in ("make", "model", "year", "goal", "contact", "contact_type", "preferred_slot_request"):
        if current_collected.get(key):
            next_collected[key] = current_collected[key]

    if other_person:
        next_collected.pop("contact", None)
        next_collected.pop("contact_type", None)

    if another_bike:
        for key in ("make", "model", "year"):
            next_collected.pop(key, None)
        next_collected.pop("preferred_slot_request", None)

    if another_bike or new_work_same_bike:
        next_collected.pop("goal", None)

    next_collected.pop("pending_additional_booking", None)

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


def _should_force_new_bike_flow(message: str) -> bool:
    return _mentions_another_bike(message) or _mentions_other_person(message)


def _should_resolve_pending_same_bike_work(collected: dict, message: str) -> bool:
    if (collected.get("pending_additional_booking") or "") != "same_bike_unspecified_work":
        return False
    return _mentions_same_work(message) or _mentions_different_work(message)


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

    inferred_goal = (
        infer_goal_from_message(message, intent)
        if _should_update_goal(booking_stage, message, entities, intent)
        else ""
    )
    if inferred_goal and not _looks_like_contact_message(inferred_goal, entities):
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

    if _should_offer_consultation_callback(booking_stage, message):
        collected["goal"] = build_consultation_goal(message, collected)
        collected["pending_callback_request"] = True
        if collected.get("contact"):
            return _finalize_consultation_request(collected, message, test_mode)
        return {
            "collected_data": collected,
            "booking_stage": "need_contact",
            "answer": "Понял. Оставьте, пожалуйста, удобный контакт, и мы свяжемся с вами в ближайшее время.",
        }

    if booking_stage in {"ready", "need_goal", "need_contact", "offer_slots"} and _should_force_new_bike_flow(message):
        return _restart_booking_after_ready(previous_collected, collected, message, intent)

    if booking_stage == "ready" and _mentions_additional_slot_same_work(message):
        return _build_same_bike_work_clarification(collected)

    if booking_stage == "ready" and _should_resolve_pending_same_bike_work(collected, message):
        return _restart_booking_after_ready(previous_collected, collected, message, intent)

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
        if _is_consultation_goal(collected):
            if collected.get("contact"):
                return _finalize_consultation_request(collected, message, test_mode)
            return {
                "collected_data": {
                    **collected,
                    "pending_callback_request": True,
                },
                "booking_stage": "need_contact",
                "answer": "Понял. Оставьте, пожалуйста, удобный контакт, и мы свяжемся с вами в ближайшее время.",
            }

        if collected.get("contact"):
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
            "booking_stage": "need_contact",
            "answer": "Хорошо. Оставьте, пожалуйста, удобный контакт: телефон, Telegram или WhatsApp.",
        }

    if booking_stage == "need_contact" and collected.get("contact"):
        if _is_consultation_goal(collected):
            return _finalize_consultation_request(collected, message, test_mode)

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
        if collected.get("pending_offer_slots_consultation_prompt"):
            if _is_yes_like(message):
                callback_collected = {
                    **collected,
                    "pending_callback_request": True,
                    "goal": build_consultation_goal(message, collected),
                }
                callback_collected.pop("pending_offer_slots_consultation_prompt", None)
                if callback_collected.get("contact"):
                    return _finalize_consultation_request(callback_collected, message, test_mode)
                return {
                    "collected_data": callback_collected,
                    "booking_stage": "need_contact",
                    "answer": "Оставьте, пожалуйста, удобный контакт, и мы свяжемся с вами в ближайшее время.",
                }

            if _is_no_like(message):
                return {
                    "collected_data": {},
                    "booking_stage": "cancelled",
                    "answer": "Понял. Тогда на сегодня остановимся. Хорошего дня, будем ждать вас, когда решите к нам обратиться.",
                }

            return {
                "collected_data": collected,
                "booking_stage": "offer_slots",
                "answer": "Нужна ли вам консультация? Если да, мы передадим заявку специалисту. Если нет, просто напишите, и на этом остановимся.",
            }

        if _is_offer_slots_hesitation(message):
            return {
                "collected_data": {
                    **collected,
                    "pending_offer_slots_consultation_prompt": True,
                },
                "booking_stage": "offer_slots",
                "answer": "Понял. Нужна ли вам консультация?",
            }

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
        if _is_consultation_goal(collected):
            if not collected.get("contact"):
                return {
                    "collected_data": {
                        **collected,
                        "pending_callback_request": True,
                    },
                    "booking_stage": "need_contact",
                    "answer": "Оставьте, пожалуйста, удобный контакт, и мы свяжемся с вами в ближайшее время.",
                }
            return _finalize_consultation_request(collected, message, test_mode)

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
