from typing import Optional
import logging
import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.db_init import init_db
from app.graph.builder import build_graph
from app.schemas.chat import ChatResponse, QuickReply, SlotItem
from app.services.lead_service import create_lead
from app.services.notification_service import notify_new_lead
from app.services.session_service import get_session, save_session
from app.services.ui_builder import enrich_result_with_ui

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


init_db()
graph = build_graph()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        logger.info("Incoming message: session_id=%s message=%s", req.session_id, req.message)

        previous = get_session(req.session_id)
        logger.info("Previous session state: %s", previous)

        state = {
            **previous,
            "user_message": req.message,
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

        if booking_stage == "ready" and not previous.get("lead_saved"):
            logger.info("Lead is ready to be saved. collected_data=%s", collected_data)

            saved_lead = create_lead(req.session_id, collected_data)
            logger.info("Lead saved successfully: %s", saved_lead)

            lead_saved = True

            telegram_result = notify_new_lead(saved_lead)
            logger.info("Telegram notification result: %s", telegram_result)

        save_session(
            req.session_id,
            {
                "collected_data": collected_data,
                "booking_stage": booking_stage,
                "lead_saved": lead_saved or previous.get("lead_saved", False),
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

    except Exception as e:
        logger.error("CHAT ERROR: %s", str(e))
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))