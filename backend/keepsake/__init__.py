"""Keepsake - a personal digital scrapbook built with Flask and MySQL."""
import mimetypes
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import pymysql
from flask import Flask, g, render_template, request, session
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db, security
from .config import load_config
from .constants import COLLECTION_EMOJIS, COLLECTION_TONES, SORTS, TYPES
from .uploads import ALLOWED_EXTENSIONS, IMAGE_EXTENSIONS
from .utils import domain_of, file_ext, fmt_date, fmt_datetime, human_size


# Some Windows setups report .css/.js as text/plain; with the nosniff header the
# browser then ignores the stylesheet. Declare the types explicitly.
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("text/javascript", ".js")


def create_app(config_overrides=None):
    frontend = Path(__file__).resolve().parent.parent.parent / "frontend"
    app = Flask(
        __name__,
        template_folder=str(frontend / "templates"),
        static_folder=str(frontend / "static"),
    )
    app.config.update(load_config())
    if config_overrides:
        app.config.update(config_overrides)
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------- request hooks
    app.teardown_appcontext(db.close_db)
    app.after_request(security.add_security_headers)

    @app.before_request
    def _guard_and_load_user():
        security.verify_csrf()
        g.user = None
        if request.endpoint in (None, "static"):
            return
        user_id = session.get("user_id")
        if user_id:
            user = db.fetch_one("SELECT id, email, display_name FROM users WHERE id = %s", (user_id,))
            if user:
                g.user = user
            else:
                session.pop("user_id", None)

    # ---------------------------------------------------------- template helpers
    def page_url(number):
        args = request.args.to_dict(flat=False)
        args["page"] = [str(number)]
        return request.path + "?" + urlencode(args, doseq=True)

    def url_without(*keys):
        args = {k: v for k, v in request.args.to_dict(flat=False).items() if k not in keys and k != "page"}
        query = urlencode(args, doseq=True)
        return request.path + ("?" + query if query else "")

    def page_window(page, pages, span=2):
        numbers = sorted({1, pages} | set(range(max(1, page - span), min(pages, page + span) + 1)))
        out, previous = [], 0
        for number in numbers:
            if number - previous > 1:
                out.append(None)
            out.append(number)
            previous = number
        return out

    def tone(value):
        return value if value in COLLECTION_TONES else "coral"

    app.jinja_env.globals.update(
        TYPES=TYPES,
        SORTS=SORTS,
        COLLECTION_TONES=COLLECTION_TONES,
        COLLECTION_EMOJIS=COLLECTION_EMOJIS,
        csrf_token=security.csrf_token,
        page_url=page_url,
        url_without=url_without,
        page_window=page_window,
    )
    app.jinja_env.filters.update(
        filesize=human_size,
        fmt_date=fmt_date,
        fmt_datetime=fmt_datetime,
        domain=domain_of,
        file_ext=file_ext,
        tone=tone,
    )

    @app.context_processor
    def _inject():
        return {
            "current_user": g.get("user"),
            "app_name": app.config["APP_NAME"],
            "max_upload_mb": app.config["MAX_UPLOAD_MB"],
            "allowed_extensions": ALLOWED_EXTENSIONS,
            "image_extensions": IMAGE_EXTENSIONS,
            "current_year": date.today().year,
        }

    # ---------------------------------------------------------- blueprints
    from . import archive, auth, main, organize

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(archive.bp)
    app.register_blueprint(organize.bp)

    # ---------------------------------------------------------- error pages
    def error_page(code, title, message):
        return render_template("errors/error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(error):
        return error_page(400, "That didn't go through", getattr(error, "description", None)
                          or "Something about that request wasn't right. Please go back and try again.")

    @app.errorhandler(403)
    def forbidden(_error):
        return error_page(403, "That's not yours to open", "You don't have access to this page.")

    @app.errorhandler(404)
    def not_found(_error):
        return error_page(404, "We couldn't find that page", "It may have been moved or deleted - or it might belong to someone else's scrapbook.")

    @app.errorhandler(413)
    def too_large(_error):
        return error_page(
            413, "That file is too big",
            f"Uploads can be up to {app.config['MAX_UPLOAD_MB']} MB. Please choose a smaller file and try again.",
        )

    @app.errorhandler(pymysql.MySQLError)
    def database_error(error):
        app.logger.exception("Database error: %s", error)
        return error_page(
            500, "The archive can't reach its database",
            "Check the DB_* settings in your .env file, make sure MySQL is running, and that you have run "
            "`python init_db.py`.",
        )

    @app.errorhandler(500)
    def server_error(_error):
        return error_page(500, "Something went wrong on our side", "Please try again in a moment.")

    return app
