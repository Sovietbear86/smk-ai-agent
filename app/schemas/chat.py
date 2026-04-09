from typing import List, Optional

from pydantic import BaseModel


class QuickReply(BaseModel):
    label: str
    value: str


class SlotItem(BaseModel):
    label: str
    value: str


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    source: Optional[str] = "website_widget"
    test_mode: bool = False


class ChatResponse(BaseModel):
    reply: str
    quick_replies: List[QuickReply] = []
    slots: List[SlotItem] = []
