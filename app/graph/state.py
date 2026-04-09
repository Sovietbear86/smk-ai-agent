from typing import TypedDict, Optional, Dict


class AgentState(TypedDict, total=False):
    user_message: str
    intent: str
    entities: Dict[str, str]
    answer: str
    booking_stage: str
    collected_data: Dict[str, str]
    test_mode: bool
    available_slots: list[str]
    quick_replies: list[dict]
