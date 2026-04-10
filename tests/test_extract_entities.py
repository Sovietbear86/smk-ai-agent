import unittest

from app.graph.nodes.extract_entities import extract_entities


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


if __name__ == "__main__":
    unittest.main()
