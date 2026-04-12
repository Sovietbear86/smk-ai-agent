import unittest

from app.services.ui_builder import enrich_result_with_ui


class UiBuilderTests(unittest.TestCase):
    def test_callback_ready_state_has_no_slot_actions(self):
        result = enrich_result_with_ui(
            {
                "booking_stage": "ready",
                "collected_data": {
                    "callback_requested": True,
                    "request_status": "need info",
                    "selected_slot": "TBD/",
                },
                "available_slots": [],
            }
        )
        self.assertEqual(result["quick_replies"], [])


if __name__ == "__main__":
    unittest.main()
