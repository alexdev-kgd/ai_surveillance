import unittest
from unittest.mock import Mock, patch

from services import sms


class SmsAeroTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event = "Нападение на камере Касса-1"

    @patch("services.sms.requests.post")
    def test_sends_notification_through_smsaero(self, post: Mock) -> None:
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.return_value = {
            "success": True,
            "data": {"id": 1, "number": "79506781834", "extendStatus": "queue"},
        }

        with (
            patch.object(sms, "SMSAERO_API_URL", "https://gate.smsaero.ru/v2"),
            patch.object(sms, "SMSAERO_EMAIL", "alerts@example.ru"),
            patch.object(sms, "SMSAERO_API_KEY", "secret-api-key"),
            patch.object(sms, "SMSAERO_PHONE", "79506781834"),
            patch.object(sms, "SMSAERO_SIGN", "SMS Aero"),
            patch.object(sms, "SMSAERO_TEST_MODE", False),
        ):
            sent = sms.send_sms_notification(self.event)

        self.assertTrue(sent)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://gate.smsaero.ru/v2/sms/send")
        self.assertEqual(kwargs["auth"], ("alerts@example.ru", "secret-api-key"))
        self.assertEqual(kwargs["headers"], {"Accept": "application/json"})
        self.assertEqual(kwargs["json"]["number"], 79506781834)
        self.assertEqual(kwargs["json"]["sign"], "SMS Aero")
        self.assertIn(self.event, kwargs["json"]["text"])
        self.assertEqual(kwargs["timeout"], sms.SMSAERO_TIMEOUT_SECONDS)

    @patch("services.sms.requests.post")
    def test_uses_testsend_when_test_mode_is_enabled(self, post: Mock) -> None:
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.return_value = {"success": True, "data": {"id": 2}}

        with (
            patch.object(sms, "SMSAERO_EMAIL", "alerts@example.ru"),
            patch.object(sms, "SMSAERO_API_KEY", "secret-api-key"),
            patch.object(sms, "SMSAERO_PHONE", "+7 (950) 678-18-34"),
            patch.object(sms, "SMSAERO_SIGN", "SMS Aero"),
            patch.object(sms, "SMSAERO_TEST_MODE", True),
        ):
            sent = sms.send_sms_notification(self.event)

        self.assertTrue(sent)
        self.assertEqual(post.call_args.args[0], "https://gate.smsaero.ru/v2/sms/testsend")
        self.assertEqual(post.call_args.kwargs["json"]["number"], 79506781834)

    @patch("services.sms.requests.post")
    def test_does_not_call_api_when_configuration_is_missing(self, post: Mock) -> None:
        with patch.object(sms, "SMSAERO_API_KEY", ""):
            sent = sms.send_sms_notification(self.event)

        self.assertFalse(sent)
        post.assert_not_called()

    @patch("services.sms.requests.post")
    def test_returns_false_when_smsaero_rejects_request(self, post: Mock) -> None:
        response = Mock(status_code=401)
        error = sms.requests.HTTPError("unauthorized", response=response)
        post.return_value.raise_for_status.side_effect = error

        with (
            patch.object(sms, "SMSAERO_EMAIL", "alerts@example.ru"),
            patch.object(sms, "SMSAERO_API_KEY", "secret-api-key"),
            patch.object(sms, "SMSAERO_PHONE", "79506781834"),
            patch.object(sms, "SMSAERO_SIGN", "SMS Aero"),
        ):
            sent = sms.send_sms_notification(self.event)

        self.assertFalse(sent)

    @patch("services.sms.requests.post")
    def test_returns_false_when_success_flag_is_false(self, post: Mock) -> None:
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.return_value = {
            "success": False,
            "message": "no credits",
        }

        with (
            patch.object(sms, "SMSAERO_EMAIL", "alerts@example.ru"),
            patch.object(sms, "SMSAERO_API_KEY", "secret-api-key"),
            patch.object(sms, "SMSAERO_PHONE", "79506781834"),
            patch.object(sms, "SMSAERO_SIGN", "SMS Aero"),
        ):
            sent = sms.send_sms_notification(self.event)

        self.assertFalse(sent)


if __name__ == "__main__":
    unittest.main()
