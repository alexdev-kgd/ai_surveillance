import logging
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from typing import Sequence

from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_TIMEOUT_SECONDS = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))

EMAIL_FROM = os.getenv("EMAIL_FROM", "") or SMTP_USER
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Видеонаблюдение магазина")
EMAIL_TO = os.getenv("EMAIL_TO", "")

NOTIFY_INTERVAL = int(os.getenv("NOTIFY_INTERVAL", "60"))

_last_notification_time = datetime.min
_buffer: list[tuple[datetime, str]] = []


def _missing_config() -> list[str]:
    config = {
        "SMTP_HOST": SMTP_HOST,
        "SMTP_USER": SMTP_USER,
        "SMTP_PASSWORD": SMTP_PASSWORD,
        "EMAIL_FROM": EMAIL_FROM,
        "EMAIL_TO": EMAIL_TO,
    }
    return [name for name, value in config.items() if not value]


def _build_message(events: Sequence[tuple[datetime, str]]) -> EmailMessage:
    body_lines = ["Обнаружены следующие подозрительные действия:", ""]
    body_lines.extend(
        f"{event_time.strftime('%H:%M:%S')} – {description}"
        for event_time, description in events
    )

    message = EmailMessage()
    message["From"] = formataddr((EMAIL_FROM_NAME, EMAIL_FROM), charset="utf-8")
    message["To"] = EMAIL_TO
    message["Subject"] = "Обнаружена подозрительная активность"
    message.set_content("\n".join(body_lines))
    return message


def send_email_notification(events: Sequence[tuple[datetime, str]]) -> bool:
    """Send a batch of suspicious events through Gmail SMTP_SSL."""
    print(f"[MAIL] Preparing to send notification for {len(events)} events")
    if not events:
        return False

    missing = _missing_config()
    if missing:
        print(f"[MAIL ERROR] Missing configuration: {', '.join(missing)}")
        logger.error("Missing mail configuration: %s", ", ".join(missing))
        return False

    message = _build_message(events)
    print(f"[MAIL] Sending SMTP message to {EMAIL_TO} via {SMTP_HOST}:{SMTP_PORT}")

    try:
        with smtplib.SMTP_SSL(
            SMTP_HOST,
            SMTP_PORT,
            timeout=SMTP_TIMEOUT_SECONDS,
        ) as server:
            server.login(SMTP_USER, SMTP_PASSWORD.strip())
            server.send_message(message)
        print(f"[MAIL] Notification sent to {EMAIL_TO} via SMTP")
        logger.info("Notification sent to %s via SMTP", EMAIL_TO)
        return True
    except smtplib.SMTPAuthenticationError as error:
        print(f"[MAIL ERROR] SMTP authentication failed: {error}")
        logger.error("SMTP authentication failed: %s", error)
        return False
    except smtplib.SMTPServerDisconnected as error:
        print(
            "[MAIL ERROR] SMTP connection closed. "
            "SMTP_USER must be the Gmail address that owns the App Password, "
            f"and EMAIL_FROM must match it. Current SMTP_USER={SMTP_USER!r}, "
            f"EMAIL_FROM={EMAIL_FROM!r}. Details: {error}"
        )
        logger.error("SMTP connection closed for %s: %s", SMTP_USER, error)
        return False
    except smtplib.SMTPException as error:
        print(f"[MAIL ERROR] SMTP send failed: {error}")
        logger.error("SMTP send failed: %s", error)
        return False
    except OSError as error:
        print(f"[MAIL ERROR] SMTP network error: {error}")
        logger.error("SMTP network error: %s", error)
        return False


def test_send_email() -> bool:
    """Send a real one-off SMTP test message using the current .env settings."""
    now = datetime.now()
    print("[MAIL] Running SMTP test_send_email()")
    return send_email_notification(
        [(now, "Тестовая проверка SMTP-уведомлений")]
    )


def add_event(event_desc: str) -> None:
    """Add a suspicious event and send the buffered events once per interval."""
    global _last_notification_time

    now = datetime.now()
    _buffer.append((now, event_desc))

    if (now - _last_notification_time).total_seconds() < NOTIFY_INTERVAL:
        return

    if send_email_notification(_buffer):
        _buffer.clear()
    _last_notification_time = now
