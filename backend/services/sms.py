import os
import re

import requests
from dotenv import load_dotenv


load_dotenv()

SMSAERO_API_URL = os.getenv("SMSAERO_API_URL", "https://gate.smsaero.ru/v2")
SMSAERO_EMAIL = os.getenv("SMSAERO_EMAIL", "")
SMSAERO_API_KEY = os.getenv("SMSAERO_API_KEY", "")
SMSAERO_SIGN = os.getenv("SMSAERO_SIGN", "SMS Aero")
SMSAERO_PHONE = os.getenv("SMSAERO_PHONE", "79506781834")
SMSAERO_TIMEOUT_SECONDS = float(os.getenv("SMSAERO_TIMEOUT_SECONDS", "10"))
SMSAERO_TEST_MODE = os.getenv("SMSAERO_TEST_MODE", "").strip().lower() in {
    "1",
    "true",
    "yes",
}


def _missing_config() -> list[str]:
    config = {
        "SMSAERO_EMAIL": SMSAERO_EMAIL,
        "SMSAERO_API_KEY": SMSAERO_API_KEY,
        "SMSAERO_PHONE": SMSAERO_PHONE,
        "SMSAERO_SIGN": SMSAERO_SIGN,
    }
    return [name for name, value in config.items() if not value]


def _normalize_phone(raw: str) -> int | None:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if not 7 <= len(digits) <= 15:
        return None
    return int(digits)


def send_sms_notification(event_desc: str) -> bool:
    """Send an SMS alert through the SMS Aero HTTP API."""
    print(f"[SMS] Уведомление: {event_desc}")

    missing = _missing_config()
    if missing:
        print(f"[SMS ERROR] Missing configuration: {', '.join(missing)}")
        return False

    phone = _normalize_phone(SMSAERO_PHONE)
    if phone is None:
        print(f"[SMS ERROR] Invalid SMSAERO_PHONE: {SMSAERO_PHONE!r}")
        return False

    message_text = f"Обнаружена подозрительная активность. Событие: {event_desc}"
    endpoint = "sms/testsend" if SMSAERO_TEST_MODE else "sms/send"
    url = f"{SMSAERO_API_URL.rstrip('/')}/{endpoint}"
    payload = {
        "number": phone,
        "text": message_text,
        "sign": SMSAERO_SIGN,
    }

    try:
        response = requests.post(
            url,
            auth=(SMSAERO_EMAIL, SMSAERO_API_KEY),
            json=payload,
            headers={"Accept": "application/json"},
            timeout=SMSAERO_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        if not body.get("success"):
            print(f"[SMS ERROR] SMS Aero rejected the request: {body.get('message')}")
            return False
        print(f"[SMS] Notification sent to {phone} via SMS Aero: {body.get('data')}")
        return True
    except requests.RequestException as error:
        status_code = error.response.status_code if error.response is not None else None
        status = f" (HTTP {status_code})" if status_code is not None else ""
        print(f"[SMS ERROR] SMS Aero request failed{status}: {error}")
        return False
    except ValueError as error:
        print(f"[SMS ERROR] SMS Aero returned a non-JSON response: {error}")
        return False
