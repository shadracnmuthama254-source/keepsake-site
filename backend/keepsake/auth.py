"""Registration, sign-in, sign-out and password reset."""
import re
import secrets

import pymysql
from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .mailer import send_email
from .security import Throttle, hash_token, safe_next
from .utils import clean_line

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8
MAX_PASSWORD = 128
RESET_MINUTES = 60

login_by_account = Throttle(limit=6, window_seconds=600)
login_by_ip = Throttle(limit=30, window_seconds=600)
reset_by_ip = Throttle(limit=5, window_seconds=900)

# Compared against when the email is unknown, so timing doesn't reveal which emails exist.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def _password_problem(password):
    if len(password) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters."
    if len(password) > MAX_PASSWORD:
        return f"Use at most {MAX_PASSWORD} characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Include at least one letter and one number."
    return None


def _start_session(user_id, remember=True):
    session.clear()  # new session id/CSRF token: protects against session fixation
    session["user_id"] = user_id
    session.permanent = remember


def _external_url(endpoint, **values):
    path = url_for(endpoint, **values)
    base = current_app.config["APP_BASE_URL"] or request.host_url.rstrip("/")
    return base + path


# ------------------------------------------------------------------ register
@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("main.index"))
    if not current_app.config["ALLOW_REGISTRATION"]:
        flash("New sign-ups are switched off on this archive.", "info")
        return redirect(url_for("auth.login"))

    errors, values = {}, {"display_name": "", "email": ""}
    if request.method == "POST":
        name = clean_line(request.form.get("display_name"))
        email = clean_line(request.form.get("email")).lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        values = {"display_name": name, "email": email}

        if not name:
            errors["display_name"] = "Tell me what to call you."
        elif len(name) > 60:
            errors["display_name"] = "Keep your name to 60 characters or fewer."
        if not EMAIL_RE.match(email) or len(email) > 254:
            errors["email"] = "Enter a valid email address."
        problem = _password_problem(password)
        if problem:
            errors["password"] = problem
        elif password != confirm:
            errors["confirm_password"] = "The two passwords don't match."

        if not errors and db.fetch_one("SELECT id FROM users WHERE email = %s", (email,)):
            errors["email"] = "That email is already registered. Try signing in instead."

        if not errors:
            try:
                with db.transaction():
                    user_id = db.insert(
                        "INSERT INTO users (email, display_name, password_hash) VALUES (%s, %s, %s)",
                        (email, name, generate_password_hash(password)),
                    )
            except pymysql.err.IntegrityError:
                errors["email"] = "That email is already registered. Try signing in instead."
            else:
                _start_session(user_id)
                flash(f"Welcome, {name}! Your scrapbook is ready. ✨", "success")
                return redirect(url_for("main.index"))

    return render_template("auth/register.html", errors=errors, values=values)


# ------------------------------------------------------------------ login / logout
@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.index"))

    errors, email = {}, ""
    next_url = request.values.get("next", "")
    if request.method == "POST":
        email = clean_line(request.form.get("email")).lower()
        password = request.form.get("password", "")
        ip = request.remote_addr or "?"
        account_key = f"{ip}|{email}"

        if login_by_account.blocked(account_key) or login_by_ip.blocked(ip):
            errors["form"] = "Too many sign-in attempts. Please wait a few minutes and try again."
        else:
            user = db.fetch_one(
                "SELECT id, display_name, password_hash FROM users WHERE email = %s", (email,)
            ) if email else None
            valid = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)
            if user and valid:
                login_by_account.reset(account_key)
                with db.transaction():
                    db.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = %s", (user["id"],))
                _start_session(user["id"], remember=request.form.get("remember") == "1")
                flash(f"Welcome back, {user['display_name']}!", "success")
                return redirect(safe_next(next_url, url_for("main.index")))
            login_by_account.hit(account_key)
            login_by_ip.hit(ip)
            errors["form"] = "That email and password don't match. Please try again."

    return render_template("auth/login.html", errors=errors, email=email, next_url=next_url)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You're signed out. See you soon! 👋", "info")
    return redirect(url_for("auth.login"))


# ------------------------------------------------------------------ password reset
@bp.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if g.user:
        return redirect(url_for("main.index"))

    errors = {}
    if request.method == "POST":
        email = clean_line(request.form.get("email")).lower()
        ip = request.remote_addr or "?"
        if reset_by_ip.blocked(ip):
            errors["form"] = "Too many reset requests. Please wait a little while and try again."
            return render_template("auth/forgot.html", errors=errors, email=email)
        reset_by_ip.hit(ip)

        user = db.fetch_one("SELECT id, email, display_name FROM users WHERE email = %s", (email,)) if email else None
        if user:
            token = secrets.token_urlsafe(32)
            with db.transaction():
                db.execute("DELETE FROM password_resets WHERE user_id = %s", (user["id"],))
                db.execute(
                    "INSERT INTO password_resets (user_id, token_hash, expires_at)"
                    " VALUES (%s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s MINUTE))",
                    (user["id"], hash_token(token), RESET_MINUTES),
                )
            link = _external_url("auth.reset_password", token=token)
            body = (
                f"Hi {user['display_name']},\n\n"
                f"Use this link to choose a new Keepsake password (valid for {RESET_MINUTES} minutes):\n\n"
                f"{link}\n\n"
                "If you didn't ask for this, you can safely ignore this email.\n"
            )
            if not send_email(user["email"], "Reset your Keepsake password", body):
                # No mail server configured: print the link in the server console instead.
                current_app.logger.warning(
                    "Mail is not configured - password reset link for %s: %s", user["email"], link
                )
        # Same answer whether or not the email exists, so accounts can't be probed.
        flash("If that email belongs to an account, a reset link is on its way.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot.html", errors=errors, email="")


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    row = None
    if 10 <= len(token) <= 128:
        row = db.fetch_one(
            "SELECT id, user_id FROM password_resets"
            " WHERE token_hash = %s AND used_at IS NULL AND expires_at > UTC_TIMESTAMP()",
            (hash_token(token),),
        )
    if not row:
        flash("That reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    errors = {}
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        problem = _password_problem(password)
        if problem:
            errors["password"] = problem
        elif password != confirm:
            errors["confirm_password"] = "The two passwords don't match."
        if not errors:
            with db.transaction():
                db.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (generate_password_hash(password), row["user_id"]),
                )
                db.execute("DELETE FROM password_resets WHERE user_id = %s", (row["user_id"],))
            session.clear()
            flash("Password updated. You can sign in with your new password.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset.html", errors=errors, token=token)
