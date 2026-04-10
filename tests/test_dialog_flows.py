import unittest
from unittest.mock import patch

from app.graph.nodes.qualification import qualification


FAKE_SLOTS = [
    {
        "slot_id": "slot_021",
        "date": "2026_04_24",
        "start_time": "15:00",
        "end_time": "17:00",
        "_row_number": 2,
    },
    {
        "slot_id": "slot_022",
        "date": "2026_04_25",
        "start_time": "16:00",
        "end_time": "18:00",
        "_row_number": 3,
    },
]


class QualificationFlowTests(unittest.TestCase):
    def _slots(self, *_args, **_kwargs):
        return list(FAKE_SLOTS)

    @patch("app.graph.nodes.qualification.get_free_slots")
    @patch("app.graph.nodes.qualification.suggest_slots_for_preference")
    def test_consultation_from_start_goes_to_callback_request(self, mock_suggest, mock_free):
        mock_suggest.return_value = []
        mock_free.side_effect = self._slots

        first = qualification(
            {
                "user_message": "Нужна консультация по настройке",
                "intent": "other",
                "entities": {},
                "booking_stage": "not_started",
                "collected_data": {},
                "test_mode": True,
            }
        )
        self.assertEqual(first["booking_stage"], "need_contact")
        self.assertIn("свяжемся", first["answer"].lower())

        second = qualification(
            {
                "user_message": "@testuser",
                "intent": "other",
                "entities": {"contact": "@testuser", "contact_type": "telegram"},
                "booking_stage": first["booking_stage"],
                "collected_data": first["collected_data"],
                "test_mode": True,
            }
        )
        self.assertEqual(second["booking_stage"], "ready")
        self.assertTrue(second["collected_data"]["callback_requested"])
        self.assertEqual(second["collected_data"]["selected_slot"], "TBD/")
        self.assertEqual(second["collected_data"]["request_status"], "need info")

    @patch("app.graph.nodes.qualification.get_free_slots")
    @patch("app.graph.nodes.qualification.suggest_slots_for_preference")
    def test_mid_booking_callback_preserves_bike_and_converts_goal(self, mock_suggest, mock_free):
        mock_suggest.return_value = []
        mock_free.side_effect = self._slots

        first = qualification(
            {
                "user_message": "пока не готов к записи, перезвоните мне",
                "intent": "booking",
                "entities": {},
                "booking_stage": "need_contact",
                "collected_data": {
                    "make": "Honda",
                    "model": "VFR",
                    "year": "2015",
                    "goal": "Нужна настройка ECU",
                },
                "test_mode": True,
            }
        )
        self.assertEqual(first["booking_stage"], "need_contact")
        self.assertIn("консультация", first["collected_data"]["goal"].lower())
        self.assertEqual(first["collected_data"]["make"], "Honda")

        second = qualification(
            {
                "user_message": "@testuser",
                "intent": "other",
                "entities": {"contact": "@testuser", "contact_type": "telegram"},
                "booking_stage": first["booking_stage"],
                "collected_data": first["collected_data"],
                "test_mode": True,
            }
        )
        self.assertEqual(second["booking_stage"], "ready")
        self.assertEqual(second["collected_data"]["selected_slot"], "TBD/")
        self.assertIn("Honda VFR 2015", second["collected_data"]["notes"])

    @patch("app.graph.nodes.qualification.get_free_slots")
    @patch("app.graph.nodes.qualification.suggest_slots_for_preference")
    def test_first_message_with_bike_goal_and_time_goes_to_slots_after_contact(self, mock_suggest, mock_free):
        mock_suggest.side_effect = lambda message, **_kwargs: self._slots() if message else []
        mock_free.side_effect = self._slots

        first = qualification(
            {
                "user_message": "Honda CBR 2020, хочу поднять мощность, в субботу после обеда",
                "intent": "booking",
                "entities": {"make": "Honda", "model": "CBR", "year": "2020"},
                "booking_stage": "not_started",
                "collected_data": {},
                "test_mode": True,
            }
        )
        self.assertEqual(first["booking_stage"], "need_contact")
        self.assertEqual(first["collected_data"]["make"], "Honda")
        self.assertIn("поднять мощность", first["collected_data"]["goal"].lower())
        self.assertIn("субботу", first["collected_data"]["preferred_slot_request"].lower())

        second = qualification(
            {
                "user_message": "@testuser",
                "intent": "other",
                "entities": {"contact": "@testuser", "contact_type": "telegram"},
                "booking_stage": first["booking_stage"],
                "collected_data": first["collected_data"],
                "test_mode": True,
            }
        )
        self.assertEqual(second["booking_stage"], "offer_slots")
        self.assertEqual(len(second["available_slots"]), 2)

    def test_unclear_bike_on_need_bike_stays_in_clarification(self):
        result = qualification(
            {
                "user_message": "блабла 1200x 2016",
                "intent": "other",
                "entities": {"model": "1200x", "year": "2016"},
                "booking_stage": "need_bike",
                "collected_data": {},
                "test_mode": True,
            }
        )
        self.assertEqual(result["booking_stage"], "need_bike")
        self.assertIn("не смог точно распознать марку", result["answer"].lower())

    @patch("app.graph.nodes.qualification.get_free_slots")
    @patch("app.graph.nodes.qualification.suggest_slots_for_preference")
    def test_pending_callback_request_survives_contact_step(self, mock_suggest, mock_free):
        mock_suggest.return_value = []
        mock_free.side_effect = self._slots

        result = qualification(
            {
                "user_message": "@testuser",
                "intent": "other",
                "entities": {"contact": "@testuser", "contact_type": "telegram"},
                "booking_stage": "need_contact",
                "collected_data": {
                    "intent": "diagnostics",
                    "goal": "Нужна консультация по настройке",
                    "pending_callback_request": True,
                },
                "test_mode": True,
            }
        )
        self.assertEqual(result["booking_stage"], "ready")
        self.assertTrue(result["collected_data"]["callback_requested"])
        self.assertNotIn("pending_callback_request", result["collected_data"])

    def test_offer_slots_hesitation_asks_about_consultation_first(self):
        result = qualification(
            {
                "user_message": "пока не готов",
                "intent": "other",
                "entities": {},
                "booking_stage": "offer_slots",
                "collected_data": {
                    "make": "Honda",
                    "model": "Transalp 650",
                    "year": "2010",
                    "goal": "настройка и замер",
                    "contact": "@testuser",
                    "contact_type": "telegram",
                    "offered_slot_ids": ["slot_021", "slot_022"],
                },
                "test_mode": True,
            }
        )
        self.assertEqual(result["booking_stage"], "offer_slots")
        self.assertTrue(result["collected_data"]["pending_offer_slots_consultation_prompt"])
        self.assertIn("нужна ли вам консультация", result["answer"].lower())

    def test_offer_slots_hesitation_yes_creates_callback_request(self):
        result = qualification(
            {
                "user_message": "да",
                "intent": "other",
                "entities": {},
                "booking_stage": "offer_slots",
                "collected_data": {
                    "make": "Honda",
                    "model": "Transalp 650",
                    "year": "2010",
                    "goal": "настройка и замер",
                    "contact": "@testuser",
                    "contact_type": "telegram",
                    "pending_offer_slots_consultation_prompt": True,
                },
                "test_mode": True,
            }
        )
        self.assertEqual(result["booking_stage"], "ready")
        self.assertTrue(result["collected_data"]["callback_requested"])
        self.assertIn("консультация по вопросу: настройка и замер", result["collected_data"]["notes"])

    def test_offer_slots_hesitation_no_finishes_politely(self):
        result = qualification(
            {
                "user_message": "в другой раз",
                "intent": "other",
                "entities": {},
                "booking_stage": "offer_slots",
                "collected_data": {
                    "pending_offer_slots_consultation_prompt": True,
                },
                "test_mode": True,
            }
        )
        self.assertEqual(result["booking_stage"], "cancelled")
        self.assertIn("хорошего дня", result["answer"].lower())

    @patch("app.graph.nodes.qualification.get_free_slots")
    @patch("app.graph.nodes.qualification.suggest_slots_for_preference")
    def test_same_bike_same_work_after_ready_returns_slots(self, mock_suggest, mock_free):
        mock_suggest.return_value = []
        mock_free.side_effect = self._slots

        first = qualification(
            {
                "user_message": "Хочу еще один слот для этого же мотоцикла",
                "intent": "booking",
                "entities": {},
                "booking_stage": "ready",
                "collected_data": {
                    "make": "Honda",
                    "model": "VFR",
                    "year": "2015",
                    "goal": "Нужна настройка ECU",
                    "contact": "@testuser",
                    "contact_type": "telegram",
                    "selected_slot": "2026_04_24 15:00-17:00",
                },
                "test_mode": True,
            }
        )
        self.assertEqual(first["booking_stage"], "ready")
        self.assertEqual(
            first["collected_data"]["pending_additional_booking"],
            "same_bike_unspecified_work",
        )

        second = qualification(
            {
                "user_message": "Тоже",
                "intent": "booking",
                "entities": {},
                "booking_stage": first["booking_stage"],
                "collected_data": first["collected_data"],
                "test_mode": True,
            }
        )
        self.assertEqual(second["booking_stage"], "offer_slots")
        self.assertEqual(len(second["available_slots"]), 2)


if __name__ == "__main__":
    unittest.main()
