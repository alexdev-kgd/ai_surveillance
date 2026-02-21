import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from email.message import EmailMessage
import requests

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO", EMAIL_FROM)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
SMS_FROM = os.getenv("SMS_FROM")
SMS_TO = os.getenv("SMS_TO")

NOTIFY_INTERVAL = int(os.getenv("NOTIFY_INTERVAL", 60))  # seconds

_last_notification_time = datetime.min
_buffer = []


def send_sms_notification(event_desc: str):
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, SMS_FROM, SMS_TO]):
        print("[SMS] Skipped: отсутствует конфигурация Twilio или номера телефона")
        return

    body = (
        "Обнаружена подозрительная активность в 10 последовательных кадрах. "
        f"Последнее событие: {event_desc}"
    )

    try:
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
            data={
                "From": SMS_FROM,
                "To": SMS_TO,
                "Body": body,
            },
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=10,
        )
        response.raise_for_status()
        print(f"[SMS] Уведомление отправлено на {SMS_TO}")
    except Exception as e:
        print(f"[SMS ERROR] {e}")


def send_email_notification(events):
    if not events:
        return

    body = "Обнаружены следующие подозрительные действия:\n\n"
    for t, desc in events:
        body += f"{t.strftime('%H:%M:%S')} – {desc}\n"

    msg = MIMEText(body)
    msg["Subject"] = "Обнаружена подозрительная активность"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)
            print(f"[MAIL] Notification sent to {EMAIL_TO}")
    except Exception as e:
        print(f"[MAIL ERROR] {e}")


def add_event(event_desc: str):
    """Add a suspicious event and check if it's time to notify."""
    global _buffer, _last_notification_time

    now = datetime.now()
    _buffer.append((now, event_desc))

    # Check if enough time has passed since the last email
    if (now - _last_notification_time).total_seconds() >= NOTIFY_INTERVAL:
        if _buffer:
            send_email_notification(_buffer)
            _buffer.clear()
        _last_notification_time = now
