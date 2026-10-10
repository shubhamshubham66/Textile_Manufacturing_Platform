"""Send transactional email through Brevo's HTTP API.

HTTP (not SMTP) because Render blocks outbound SMTP ports. The API key and the
sender address come from settings; nothing is hard-coded.
"""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


class EmailNotConfigured(RuntimeError):
    """BREVO_API_KEY or MAIL_FROM_EMAIL is missing."""


class EmailSendFailed(RuntimeError):
    """Brevo rejected the request or could not be reached."""


def email_configured() -> bool:
    s = get_settings()
    return bool(s.brevo_api_key and s.mail_from_email)


def send_email(to: str, subject: str, text: str, html: str) -> None:
    s = get_settings()
    if not email_configured():
        raise EmailNotConfigured("Email sending is not set up on the server.")
    try:
        res = httpx.post(
            BREVO_URL,
            headers={"api-key": s.brevo_api_key, "accept": "application/json"},
            json={
                "sender": {"email": s.mail_from_email, "name": s.mail_from_name},
                "to": [{"email": to}],
                "subject": subject,
                "textContent": text,
                "htmlContent": html,
            },
            timeout=15,
        )
    except httpx.HTTPError as exc:
        log.warning("Brevo request failed: %s", exc)
        raise EmailSendFailed("Could not reach the email service.") from exc
    if res.status_code >= 300:
        # Log Brevo's reason for us; don't show it to the user.
        log.warning("Brevo rejected email (%s): %s", res.status_code, res.text[:300])
        raise EmailSendFailed("The email service rejected the message.")


def send_signup_otp(to: str, code: str, minutes: int) -> None:
    subject = f"{code} is your Everest Textile Mills code"
    text = (
        f"Your Everest Textile Mills signup code is {code}.\n"
        f"It expires in {minutes} minutes. If you didn't ask for it, ignore this email."
    )
    html = (
        "<div style=\"font-family:Arial,sans-serif;font-size:15px;color:#1b2a6b\">"
        "<p>Your Everest Textile Mills signup code is:</p>"
        f"<p style=\"font-size:28px;font-weight:700;letter-spacing:6px\">{code}</p>"
        f"<p>It expires in {minutes} minutes. If you didn't ask for it, ignore this email.</p>"
        "</div>"
    )
    send_email(to, subject, text, html)
