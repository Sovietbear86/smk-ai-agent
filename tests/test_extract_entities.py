import unittest

from app.graph.nodes.extract_entities import extract_entities
from app.services.availability_service import build_consultation_goal, normalize_goal


class ExtractEntitiesTests(unittest.TestCase):
    def test_transalp_alias_is_normalized(self):
        result = extract_entities({"user_message": "трансляп 650 2006"})
        entities = result["entities"]

        self.assertEqual(entities.get("make"), "Honda")
        self.assertEqual(entities.get("model"), "Transalp 650")
        self.assertEqual(entities.get("year"), "2006")

    def test_contact_is_extracted_from_telegram_handle(self):
        result = extract_entities({"user_message": "мой контакт @testuser"})
        entities = result["entities"]

        self.assertEqual(entities.get("contact"), "@testuser")
        self.assertEqual(entities.get("contact_type"), "telegram")

    def test_year_and_model_do_not_become_phone_number(self):
        result = extract_entities({"user_message": "Голда 1800 2012"})
        entities = result["entities"]

        self.assertNotIn("contact", entities)
        self.assertEqual(entities.get("year"), "2012")

    def test_consultation_goal_is_not_double_prefixed(self):
        goal = build_consultation_goal(
            "да",
            {
                "goal": "консультация по вопросу: настройка и замер",
                "intent": "other",
            },
        )
        self.assertEqual(goal, "консультация по вопросу: настройка и замер")

    def test_normalize_goal_prefers_consultation_over_tuning_tokens(self):
        normalized = normalize_goal("консультация по настройке", "other")
        self.assertEqual(normalized, "консультация")


if __name__ == "__main__":
    unittest.main()
