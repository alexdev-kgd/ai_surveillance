import smtplib
import unittest
from contextlib import ExitStack, contextmanager
from datetime import datetime
from email.utils import parseaddr
from unittest.mock import Mock, patch

from services import mail


class SmtpMailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = [(datetime(2026, 9, 4, 12, 30, 45), "Движение на камере 1")]

    @contextmanager
    def _patched_config(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(mail, "SMTP_HOST", "smtp.gmail.com"))
            stack.enter_context(patch.object(mail, "SMTP_PORT", 465))
            stack.enter_context(patch.object(mail, "SMTP_USER", "alerts@gmail.com"))
            stack.enter_context(patch.object(mail, "SMTP_PASSWORD", "app-password"))
            stack.enter_context(patch.object(mail, "SMTP_TIMEOUT_SECONDS", 10.0))
            stack.enter_context(patch.object(mail, "EMAIL_FROM", "alerts@gmail.com"))
            stack.enter_context(patch.object(mail, "EMAIL_FROM_NAME", "Видеонаблюдение магазина"))
            stack.enter_context(patch.object(mail, "EMAIL_TO", "operator@example.ru"))
            yield

    @patch("services.mail.smtplib.SMTP_SSL")
    def test_sends_notification_through_smtp(self, smtp_ssl: Mock) -> None:
        server = smtp_ssl.return_value.__enter__.return_value

        with self._patched_config():
            sent = mail.send_email_notification(self.events)

        self.assertTrue(sent)
        smtp_ssl.assert_called_once_with("smtp.gmail.com", 465, timeout=10.0)
        server.login.assert_called_once_with("alerts@gmail.com", "app-password")
        server.send_message.assert_called_once()

        message = server.send_message.call_args.args[0]
        self.assertEqual(parseaddr(message["From"]), ("Видеонаблюдение магазина", "alerts@gmail.com"))
        self.assertEqual(message["To"], "operator@example.ru")
        self.assertEqual(message["Subject"], "Обнаружена подозрительная активность")
        self.assertIn("Движение на камере 1", message.get_content())

    @patch("services.mail.smtplib.SMTP_SSL")
    def test_does_not_connect_when_configuration_is_missing(self, smtp_ssl: Mock) -> None:
        with patch.object(mail, "SMTP_PASSWORD", ""):
            sent = mail.send_email_notification(self.events)

        self.assertFalse(sent)
        smtp_ssl.assert_not_called()

    @patch("services.mail.smtplib.SMTP_SSL")
    def test_returns_false_when_authentication_fails(self, smtp_ssl: Mock) -> None:
        smtp_ssl.return_value.__enter__.return_value.login.side_effect = (
            smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
        )

        with self._patched_config():
            sent = mail.send_email_notification(self.events)

        self.assertFalse(sent)

    @patch("services.mail.smtplib.SMTP_SSL")
    def test_returns_false_when_smtp_raises(self, smtp_ssl: Mock) -> None:
        smtp_ssl.return_value.__enter__.return_value.send_message.side_effect = (
            smtplib.SMTPException("send failed")
        )

        with self._patched_config():
            sent = mail.send_email_notification(self.events)

        self.assertFalse(sent)

    @patch("services.mail.smtplib.SMTP_SSL")
    def test_returns_false_on_network_error(self, smtp_ssl: Mock) -> None:
        smtp_ssl.side_effect = OSError("connection refused")

        with self._patched_config():
            sent = mail.send_email_notification(self.events)

        self.assertFalse(sent)


if __name__ == "__main__":
    unittest.main()
