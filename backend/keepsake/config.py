"""Application configuration.

Everything sensitive (database credentials, secret key, mail password) is read
from environment variables, which are loaded from a local ``.env`` file. The
values never reach the browser and the real ``.env`` is git-ignored.
"""
import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

log = logging.getLogger(__name__)


def _env(name, default="", strip=True):
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip() if strip else value
    return default if value == "" and strip else value


def _bool(name, default=False):
    value = _env(name, "")
    if value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _int(name, default):
    raw = _env(name, str(default))
    try:
        return int(raw)
    except ValueError:
        log.warning("%s=%r is not a number; using %s", name, raw, default)
        return default


def load_config():
    secret_key = _env("SECRET_KEY")
    if not secret_key or secret_key.startswith("change-me"):
        log.warning(
            "SECRET_KEY is not set in .env - using a temporary key. "
            "You will be signed out every time the server restarts."
        )
        secret_key = secrets.token_hex(32)

    upload_dir = Path(_env("UPLOAD_DIR", str(BASE_DIR / "instance" / "uploads")))
    if not upload_dir.is_absolute():
        upload_dir = BASE_DIR / upload_dir

    max_upload_mb = max(1, _int("MAX_UPLOAD_MB", 15))

    return {
        "APP_NAME": "Keepsake",
        "SECRET_KEY": secret_key,
        "DEBUG": _bool("FLASK_DEBUG", False),
        "HOST": _env("HOST", "127.0.0.1"),
        "PORT": _int("PORT", 5000),
        # --- database ---
        "DB_HOST": _env("DB_HOST", "127.0.0.1"),
        "DB_PORT": _int("DB_PORT", 3306),
        "DB_NAME": _env("DB_NAME", "keepsake"),
        "DB_USER": _env("DB_USER", "root"),
        "DB_PASSWORD": _env("DB_PASSWORD", "", strip=False),
        # --- uploads ---
        "UPLOAD_FOLDER": str(upload_dir),
        "MAX_UPLOAD_MB": max_upload_mb,
        # Room for the other form fields on top of the file itself.
        "MAX_CONTENT_LENGTH": (max_upload_mb + 1) * 1024 * 1024,
        # --- sessions & cookies ---
        "SESSION_COOKIE_NAME": "keepsake_session",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": _bool("SESSION_COOKIE_SECURE", False),
        "PERMANENT_SESSION_LIFETIME": _int("SESSION_DAYS", 14) * 24 * 3600,
        # --- accounts ---
        "ALLOW_REGISTRATION": _bool("ALLOW_REGISTRATION", True),
        "APP_BASE_URL": _env("APP_BASE_URL", "").rstrip("/"),
        "TRUST_PROXY": _bool("TRUST_PROXY", False),
        # --- outgoing mail (optional; used for password reset links) ---
        "MAIL_SERVER": _env("MAIL_SERVER", ""),
        "MAIL_PORT": _int("MAIL_PORT", 587),
        "MAIL_USERNAME": _env("MAIL_USERNAME", ""),
        "MAIL_PASSWORD": _env("MAIL_PASSWORD", "", strip=False),
        "MAIL_USE_TLS": _bool("MAIL_USE_TLS", True),
        "MAIL_USE_SSL": _bool("MAIL_USE_SSL", False),
        "MAIL_FROM": _env("MAIL_FROM", "Keepsake <no-reply@localhost>"),
    }
