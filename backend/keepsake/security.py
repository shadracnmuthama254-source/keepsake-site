"""CSRF protection, security headers, login guard, throttling, safe redirects."""
import hashlib
import hmac
import secrets
import threading
import time
from functools import wraps
from urllib.parse import urlparse

from flask import abort, current_app, flash, g, redirect, request, session, url_for


# ---------------------------------------------------------------- CSRF
def csrf_token():
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def verify_csrf():
    """Reject any state-changing request that lacks the session's CSRF token."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    expected = session.get("_csrf", "")
    if not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
        abort(400, description="Your form expired or was not valid. Please go back, refresh the page and try again.")


# ---------------------------------------------------------------- headers
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "script-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
    )
    if current_app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    if g.get("user") is not None:
        # Pages show personal content: keep them out of shared caches.
        response.headers.setdefault("Cache-Control", "private, no-cache")
    return response


# ---------------------------------------------------------------- auth guard
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            flash("Please sign in to open your archive.", "info")
            target = request.full_path.rstrip("?") if request.method == "GET" else None
            return redirect(url_for("auth.login", next=target))
        return view(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------- redirects
def safe_next(target, default):
    """Only allow same-site relative paths as redirect targets."""
    if not target:
        return default
    target = target.strip()
    if (
        not target.startswith("/")
        or target.startswith("//")
        or "\\" in target
        or any(ord(ch) < 32 for ch in target)
    ):
        return default
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return default
    return target


# ---------------------------------------------------------------- tokens
def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------- throttling
class Throttle:
    """Tiny in-memory attempt limiter (per process). Good enough for a personal site."""

    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self._hits = {}
        self._lock = threading.Lock()

    def _recent(self, key, now):
        recent = [t for t in self._hits.get(key, []) if now - t < self.window]
        if recent:
            self._hits[key] = recent
        else:
            self._hits.pop(key, None)
        return recent

    def blocked(self, key):
        with self._lock:
            return len(self._recent(key, time.monotonic())) >= self.limit

    def hit(self, key):
        with self._lock:
            now = time.monotonic()
            if len(self._hits) > 5000:
                self._hits.clear()
            self._recent(key, now)
            self._hits.setdefault(key, []).append(now)

    def reset(self, key):
        with self._lock:
            self._hits.pop(key, None)
