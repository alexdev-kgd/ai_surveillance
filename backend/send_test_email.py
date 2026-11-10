"""Send a real SMTP test message using values from backend/.env."""

from services.mail import test_send_email


if __name__ == "__main__":
    ok = test_send_email()
    raise SystemExit(0 if ok else 1)
