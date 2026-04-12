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
        self.assertIn("\u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0438\u044f", first["collected_data"]["goal"].lower())
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
        self.assertTrue(
            any(
                token in first["collected_data"]["goal"].lower()
                for token in ("\u043f\u043e\u0434\u043d\u044f\u0442\u044c \u043c\u043e\u0449\u043d\u043e\u0441\u0442\u044c", "\u043f\u043e\u0434\u043d\u044f\u0442\u0438\u0435 \u043c\u043e\u0449\u043d\u043e\u0441\u0442\u0438")
            )
        )
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
        self.assertNotEqual(result["collected_data"]["goal"], "@testuser")

    @patch("app.graph.nodes.qualification.get_free_slots")
    @patch("app.graph.nodes.qualification.suggest_slots_for_preference")
    def test_contact_message_does_not_become_callback_goal(self, mock_suggest, mock_free):
        mock_suggest.return_value = []
        mock_free.side_effect = self._slots

        result = qualification(
            {
                "user_message": "89169333686",
                "intent": "contacts",
                "entities": {"contact": "89169333686"},
                "booking_stage": "need_contact",
                "collected_data": {
                    "year": "2018",
                    "make": "Honda",
                    "model": "Gold Wing",
                    "intent": "diagnostics",
                    "pending_callback_request": True,
                },
                "test_mode": True,
            }
        )
        self.assertEqual(result["booking_stage"], "ready")
        self.assertEqual(result["collected_data"]["contact"], "89169333686")
        self.assertNotEqual(result["collected_data"]["goal"], "89169333686")
        self.assertIn("goal=консультация", result["collected_data"]["notes"])
        self.assertIn("contact=89169333686", result["collected_data"]["notes"])

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

    def test_diagnostic_question_for_golda_goes_straight_to_contact(self):
        result = qualification(
            {
                "user_message": "\u041f\u0440\u0438\u0432\u0435\u0442! \u0443 \u043c\u0435\u043d\u044f \u0433\u043e\u043b\u0434\u0430 2018. \u0441\u0442\u0430\u043b\u0430 \u043f\u043b\u043e\u0445\u043e \u0442\u044f\u043d\u0443\u0442\u044c \u043d\u0430 \u0432\u044b\u0441\u043e\u043a\u0438\u0445 \u0438 \u043c\u043d\u043e\u0433\u043e \u0436\u0440\u0430\u0442\u044c \u0431\u0435\u043d\u0437\u0430. \u0427\u0442\u043e \u0441\u0434\u0435\u043b\u0430\u0442\u044c?",
                "intent": "diagnostics",
                "entities": {"make": "Honda", "model": "Gold Wing", "year": "2018"},
                "booking_stage": "not_started",
                "collected_data": {},
                "test_mode": True,
            }
        )
        self.assertEqual(result["booking_stage"], "need_contact")
        self.assertTrue(result["collected_data"]["pending_callback_request"])
        self.assertIn("свяжемся", result["answer"].lower())

    def test_direct_dyno_request_stays_in_booking_flow(self):
        result = qualification(
            {
                "user_message": "\u0418\u043d\u0442\u0435\u0440\u0435\u0441\u0443\u0435\u0442 \u0437\u0430\u043c\u0435\u0440 \u043d\u0430 \u0434\u0438\u043d\u043e\u0441\u0442\u0435\u043d\u0434\u0435",
                "intent": "dyno",
                "entities": {},
                "booking_stage": "not_started",
                "collected_data": {},
                "test_mode": True,
            }
        )
        self.assertEqual(result["booking_stage"], "need_bike")
        self.assertNotIn("pending_callback_request", result["collected_data"])

    def test_direct_ecu_request_stays_in_booking_flow(self):
        result = qualification(
            {
                "user_message": "\u0418\u043d\u0442\u0435\u0440\u0435\u0441\u0443\u0435\u0442 \u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430 ECU",
                "intent": "ecu",
                "entities": {},
                "booking_stage": "not_started",
                "collected_data": {},
                "test_mode": True,
            }
        )
        self.assertEqual(result["booking_stage"], "need_bike")
        self.assertNotIn("pending_callback_request", result["collected_data"])


    def test_explicit_booking_goal_clears_pending_callback_mode(self):
        result = qualification(
            {
                "user_message": "Интересует настройка ECU",
                "intent": "ecu",
                "entities": {},
                "booking_stage": "need_contact",
                "collected_data": {
                    "year": "2016",
                    "make": "BMW",
                    "model": "1600",
                    "intent": "diagnostics",
                    "goal": "Привет! интересует увеличение мощности мотоцикла",
                    "pending_callback_request": True,
                },
                "test_mode": True,
            }
        )
        self.assertEqual(result["booking_stage"], "need_contact")
        self.assertEqual(result["collected_data"]["goal"], "Интересует настройка ECU")
        self.assertNotIn("pending_callback_request", result["collected_data"])


if __name__ == "__main__":
    unittest.main()
