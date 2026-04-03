from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


class KnowledgeService:
    def __init__(self, path: str = "knowledge/faq_kb.csv") -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Knowledge base file not found: {self.path}")
        self.df = pd.read_csv(self.path)

    def find_answer(self, message: str) -> Optional[dict]:
        normalized_message = message.lower().strip()

        for _, row in self.df.iterrows():
            if not bool(row.get("is_active", True)):
                continue

            patterns = str(row["question_patterns"]).lower().split(";")
            if any(pattern.strip() and pattern.strip() in normalized_message for pattern in patterns):
                return {
                    "id": row["id"],
                    "answer": row["canonical_answer"],
                    "followup": row.get("followup_question", "") or "",
                    "category": row.get("category", "other"),
                }

        return None


knowledge_service = KnowledgeService()
