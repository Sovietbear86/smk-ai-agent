import unittest

from app.graph.nodes.extract_entities import extract_entities
from app.services.availability_service import build_consultation_goal, normalize_goal


class ExtractEntitiesTests(unittest.TestCase):
    def test_golda_alias_is_normalized_inside_long_phrase(self):
        result = extract_entities(
            {
                "user_message": "\u041f\u0440\u0438\u0432\u0435\u0442! \u0443 \u043c\u0435\u043d\u044f \u0433\u043e\u043b\u0434\u0430 2018. \u0441\u0442\u0430\u043b\u0430 \u043f\u043b\u043e\u0445\u043e \u0442\u044f\u043d\u0443\u0442\u044c \u043d\u0430 \u0432\u044b\u0441\u043e\u043a\u0438\u0445."
            }
        )
        entities = result["entities"]

        self.assertEqual(entities.get("make"), "Honda")
        self.assertEqual(entities.get("model"), "Gold Wing")
        self.assertEqual(entities.get("year"), "2018")

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


    def test_normalize_goal_does_not_infer_from_empty_string(self):
        self.assertEqual(normalize_goal("", "diagnostics"), "")
        self.assertEqual(normalize_goal("", "contacts"), "")

if __name__ == "__main__":
    unittest.main()
