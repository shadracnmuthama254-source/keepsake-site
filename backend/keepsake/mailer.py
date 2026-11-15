"""Optional outgoing email (used for password reset links)."""
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def send_email(to_address, subject, body):
    """Send a plain-text email. Returns True on success, False if mail is not
    configured or sending failed (the caller decides how to fall back)."""
    cfg = current_app.config
    if not cfg["MAIL_SERVER"]:
        return False

    message = EmailMessage()
    message["From"] = cfg["MAIL_FROM"]
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    try:
        context = ssl.create_default_context()
        if cfg["MAIL_USE_SSL"]:
            server = smtplib.SMTP_SSL(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15, context=context)
        else:
            server = smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15)
        with server:
            if cfg["MAIL_USE_TLS"] and not cfg["MAIL_USE_SSL"]:
                server.starttls(context=context)
            if cfg["MAIL_USERNAME"]:
                server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            server.send_message(message)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        current_app.logger.error("Could not send email: %s", exc)
        return False
