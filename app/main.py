import logging
import traceback

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db_init import init_db
from app.graph.builder import build_graph
from app.schemas.chat import ChatRequest, ChatResponse, QuickReply, SlotItem
from app.services.health_service import check_google_sheets, check_openai, check_telegram
from app.services.lead_service import create_lead
from app.services.notification_service import notify_new_lead
from app.services.reminder_service import send_incomplete_booking_reminders, send_visit_reminders
from app.services.session_service import get_session, save_session
from app.services.telegram_webhook_service import process_telegram_update
from app.services.ui_builder import enrich_result_with_ui
from app.integrations.telegram_bot import telegram_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    openai_result = check_openai()
    google_result = check_google_sheets()
    telegram_result = check_telegram()

    overall_ok = all(
        result.get("ok")
        for result in (openai_result, google_result, telegram_result)
    )

    return {
        "ok": overall_ok,
        "services": {
            "openai": openai_result,
            "google_sheets": google_result,
            "telegram": telegram_result,
        },
    }


@app.post("/reminders/run")
def run_reminders(older_than_minutes: int = 60):
    return send_incomplete_booking_reminders(older_than_minutes=older_than_minutes)


@app.post("/reminders/visits/run")
def run_visit_reminders(window_start_hours: int = 23, window_end_hours: int = 25):
    return send_visit_reminders(
        window_start_hours=window_start_hours,
        window_end_hours=window_end_hours,
    )


@app.post("/telegram/webhook")
def telegram_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    expected_secret = telegram_bot.webhook_secret
    if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
        raise HTTPException(status_code=403, detail="invalid telegram webhook secret")

    return process_telegram_update(update)


init_db()
graph = build_graph()


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        logger.info(
            "Incoming message: session_id=%s source=%s test_mode=%s message=%s",
            req.session_id,
            req.source,
            req.test_mode,
            req.message,
        )

        previous = get_session(req.session_id)
        logger.info("Previous session state: %s", previous)

        state = {
            **previous,
            "user_message": req.message,
            "test_mode": req.test_mode,
        }

        result = graph.invoke(state)
        result = enrich_result_with_ui(result)

        logger.info("Graph result: %s", result)

        booking_stage = result.get(
            "booking_stage",
            previous.get("booking_stage", "not_started"),
        )
        collected_data = result.get(
            "collected_data",
            previous.get("collected_data", {}),
        )

        lead_saved = False
        saved_lead = None
        telegram_result = None
        previous_selected_slot = (previous.get("collected_data") or {}).get("selected_slot")
        current_selected_slot = collected_data.get("selected_slot")
        should_save_lead = (
            booking_stage == "ready"
            and not req.test_mode
            and (
                not previous.get("lead_saved")
                or (
                    current_selected_slot
                    and current_selected_slot != previous_selected_slot
                )
            )
        )

        if should_save_lead:
            logger.info("Lead is ready to be saved. collected_data=%s", collected_data)

            saved_lead = create_lead(req.session_id, collected_data)
            logger.info("Lead saved successfully: %s", saved_lead)

            lead_saved = True

            telegram_result = notify_new_lead(saved_lead)
            logger.info("Telegram notification result: %s", telegram_result)
        elif booking_stage == "ready" and req.test_mode:
            logger.info("Test mode enabled: skipping lead save and telegram notification")

        save_session(
            req.session_id,
            {
                "collected_data": collected_data,
                "booking_stage": booking_stage,
                "lead_saved": booking_stage == "ready" and not req.test_mode,
                "reminder_sent_at": None if booking_stage in {"need_contact", "offer_slots"} else previous.get("reminder_sent_at"),
                "visit_reminder_sent_at": previous.get("visit_reminder_sent_at"),
                "clear_reminder_sent_at": booking_stage in {"need_contact", "offer_slots"},
            },
        )
        logger.info("Session saved successfully")

        reply = result.get("answer", "Извините, не удалось сформировать ответ.")

        if lead_saved:
            slot = collected_data.get("selected_slot")
            if slot:
                reply = f"Записали вас на {slot}. Мы свяжемся с вами для подтверждения."
            else:
                reply = "Заявка сохранена. Мы свяжемся с вами для подтверждения деталей."
        elif booking_stage == "ready" and req.test_mode:
            slot = collected_data.get("selected_slot")
            if slot:
                reply = f"Тестовый режим: выбрали слот {slot}, но ничего не сохранили и не отправили."
            else:
                reply = "Тестовый режим: данные собраны, но лид не сохранён и уведомление не отправлено."

        quick_replies = [
            QuickReply(label=item["label"], value=item["value"])
            for item in result.get("quick_replies", [])
        ]

        slots = [
            SlotItem(label=item, value=f"Выбираю слот {item}")
            for item in result.get("available_slots", [])
        ]

        return ChatResponse(
            reply=reply,
            quick_replies=quick_replies,
            slots=slots,
        )

    except Exception as exc:
        logger.error("CHAT ERROR: %s", str(exc))
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc))
