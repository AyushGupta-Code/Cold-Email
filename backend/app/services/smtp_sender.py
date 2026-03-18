from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import Settings
from app.schemas.api import SendEmailRequest, SettingsTestResponse


def is_smtp_configured(settings: Settings) -> bool:
    return bool(settings.smtp_enabled and settings.smtp_host and settings.smtp_sender_email)


def send_email(request: SendEmailRequest, settings: Settings) -> tuple[bool, str]:
    if not is_smtp_configured(settings):
        return False, "SMTP is not configured. Update settings first."

    message = EmailMessage()
    message["From"] = settings.smtp_sender_email
    message["To"] = request.to_email
    message["Subject"] = request.subject
    message.set_content(request.body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.ehlo()
            if settings.smtp_use_tls:
                server.starttls()
                server.ehlo()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return True, "Email sent successfully."
    except Exception as exc:
        return False, f"SMTP send failed: {exc}"


def test_smtp_connection(settings: Settings) -> SettingsTestResponse:
    if not settings.smtp_host:
        return SettingsTestResponse(ok=False, message="SMTP host is not configured.")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            if settings.smtp_use_tls:
                server.starttls()
                server.ehlo()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
        return SettingsTestResponse(
            ok=True,
            message="SMTP connection succeeded.",
            details={"host": settings.smtp_host, "port": settings.smtp_port},
        )
    except Exception as exc:
        return SettingsTestResponse(ok=False, message=f"SMTP connection failed: {exc}")

