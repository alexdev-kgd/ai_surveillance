import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from services import mail


class RuSenderMailTests(unittest.TestCase):
    def setUp(self):
        self.events = [(datetime(2026, 9, 4, 12, 30, 45), "Движение на камере 1")]

    @patch("services.mail.requests.post")
    def test_sends_notification_through_rusender(self, post: Mock) -> None:
        post.return_value.raise_for_status.return_value = None

        with (
            patch.object(mail, "RUSENDER_API_URL", "https://api.rusender.ru"),
            patch.object(mail, "RUSENDER_API_TOKEN", "secret-token"),
            patch.object(mail, "RUSENDER_KEY_ID", "42"),
            patch.object(mail, "EMAIL_FROM", "alerts@example.ru"),
            patch.object(mail, "EMAIL_FROM_NAME", "Security"),
            patch.object(mail, "EMAIL_TO", "operator@example.ru"),
        ):
            sent = mail.send_email_notification(self.events)

        self.assertTrue(sent)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(
            args[0],
            "https://api.rusender.ru/api/v1/external-mails/send/42",
        )
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer secret-token"})
        self.assertEqual(kwargs["json"]["mail"]["to"]["email"], "operator@example.ru")
        self.assertEqual(kwargs["json"]["mail"]["from"]["email"], "alerts@example.ru")
        self.assertIn("Движение на камере 1", kwargs["json"]["mail"]["text"])
        self.assertEqual(kwargs["timeout"], mail.RUSENDER_TIMEOUT_SECONDS)

    @patch("services.mail.requests.post")
    def test_does_not_call_api_when_configuration_is_missing(self, post: Mock) -> None:
        with patch.object(mail, "RUSENDER_API_TOKEN", ""):
            sent = mail.send_email_notification(self.events)

        self.assertFalse(sent)
        post.assert_not_called()

    @patch("services.mail.requests.post")
    def test_returns_false_when_rusender_rejects_request(self, post: Mock) -> None:
        response = Mock(status_code=401)
        error = mail.requests.HTTPError("unauthorized", response=response)
        post.return_value.raise_for_status.side_effect = error

        with (
            patch.object(mail, "RUSENDER_API_TOKEN", "secret-token"),
            patch.object(mail, "RUSENDER_KEY_ID", "42"),
            patch.object(mail, "EMAIL_FROM", "alerts@example.ru"),
            patch.object(mail, "EMAIL_TO", "operator@example.ru"),
        ):
            sent = mail.send_email_notification(self.events)

        self.assertFalse(sent)


if __name__ == "__main__":
    unittest.main()
