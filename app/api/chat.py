from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse, QuickReply, SlotItem

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_handler(payload: ChatRequest):
    message = payload.message.lower()

    if "запис" in message or "слот" in message:
        return ChatResponse(
            reply="Вот ближайшие доступные слоты:",
            slots=[
                SlotItem(
                    label="Пн, 8 апреля — 12:00",
                    value="Выбираю слот Пн, 8 апреля — 12:00",
                ),
                SlotItem(
                    label="Пн, 8 апреля — 15:00",
                    value="Выбираю слот Пн, 8 апреля — 15:00",
                ),
                SlotItem(
                    label="Вт, 9 апреля — 11:00",
                    value="Выбираю слот Вт, 9 апреля — 11:00",
                ),
            ],
        )

    if "ecu" in message or "настрой" in message:
        return ChatResponse(
            reply="Подскажите, пожалуйста, марку, модель и год мотоцикла.",
            quick_replies=[
                QuickReply(label="Honda", value="Honda"),
                QuickReply(label="BMW", value="BMW"),
                QuickReply(label="Yamaha", value="Yamaha"),
                QuickReply(label="Kawasaki", value="Kawasaki"),
            ],
        )

    return ChatResponse(
        reply="Здравствуйте. Помогу с настройкой ECU, диностендом и записью. Что вас интересует?",
        quick_replies=[
            QuickReply(label="Настройка ECU", value="Интересует настройка ECU"),
            QuickReply(label="Запись на диностенд", value="Хочу записаться на диностенд"),
            QuickReply(label="Подбор тюнинга", value="Нужна консультация по тюнингу"),
        ],
    )