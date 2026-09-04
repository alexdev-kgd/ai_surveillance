import hashlib
import os
from datetime import datetime
from typing import Sequence

import requests
from dotenv import load_dotenv


load_dotenv()

RUSENDER_API_URL = os.getenv("RUSENDER_API_URL", "https://api.rusender.ru")
RUSENDER_API_TOKEN = os.getenv("RUSENDER_API_TOKEN", "")
RUSENDER_KEY_ID = os.getenv("RUSENDER_KEY_ID", "")
RUSENDER_TIMEOUT_SECONDS = float(os.getenv("RUSENDER_TIMEOUT_SECONDS", "10"))

EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "AI Surveillance")
EMAIL_TO = os.getenv("EMAIL_TO", "")

NOTIFY_INTERVAL = int(os.getenv("NOTIFY_INTERVAL", "60"))

_last_notification_time = datetime.min
_buffer: list[tuple[datetime, str]] = []


def _idempotency_key(events: Sequence[tuple[datetime, str]]) -> str:
    serialized_events = "\n".join(
        f"{event_time.isoformat()}|{description}"
        for event_time, description in events
    )
    digest = hashlib.sha256(serialized_events.encode("utf-8")).hexdigest()
    return f"ai-surveillance-{digest}"


def _missing_config() -> list[str]:
    config = {
        "RUSENDER_API_TOKEN": RUSENDER_API_TOKEN,
        "RUSENDER_KEY_ID": RUSENDER_KEY_ID,
        "EMAIL_FROM": EMAIL_FROM,
        "EMAIL_TO": EMAIL_TO,
    }
    return [name for name, value in config.items() if not value]


def send_email_notification(events: Sequence[tuple[datetime, str]]) -> bool:
    """Send a batch of suspicious events through the RuSender Email API."""
    if not events:
        return False

    missing = _missing_config()
    if missing:
        print(f"[MAIL ERROR] Missing configuration: {', '.join(missing)}")
        return False

    body_lines = ["Обнаружены следующие подозрительные действия:", ""]
    body_lines.extend(
        f"{event_time.strftime('%H:%M:%S')} – {description}"
        for event_time, description in events
    )

    payload = {
        "idempotencyKey": _idempotency_key(events),
        "mail": {
            "to": {"email": EMAIL_TO},
            "from": {"email": EMAIL_FROM, "name": EMAIL_FROM_NAME},
            "subject": "Обнаружена подозрительная активность",
            "text": "\n".join(body_lines),
        },
    }
    url = (
        f"{RUSENDER_API_URL.rstrip('/')}"
        f"/api/v1/external-mails/send/{RUSENDER_KEY_ID}"
    )

    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {RUSENDER_API_TOKEN}"},
            json=payload,
            timeout=RUSENDER_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        print(f"[MAIL] Notification sent to {EMAIL_TO} via RuSender")
        return True
    except requests.RequestException as error:
        status_code = error.response.status_code if error.response is not None else None
        status = f" (HTTP {status_code})" if status_code is not None else ""
        print(f"[MAIL ERROR] RuSender request failed{status}: {error}")
        return False


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
