"""Landing page (signed out) and dashboard (signed in)."""
from datetime import date, datetime

from flask import Blueprint, g, render_template

from . import db
from .constants import TYPES
from .queries import ITEM_SELECT, attach_tags, user_collections

bp = Blueprint("main", __name__)


def _greeting(hour):
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    if 17 <= hour < 22:
        return "Good evening"
    return "Hello, night owl"


@bp.route("/")
def index():
    if g.user is None:
        return render_template("landing.html")

    uid = g.user["id"]
    counts = {key: 0 for key in TYPES}
    for row in db.fetch_all("SELECT type, COUNT(*) AS n FROM items WHERE user_id = %s GROUP BY type", (uid,)):
        counts[row["type"]] = row["n"]
    total = sum(counts.values())

    recent = db.fetch_all(
        f"{ITEM_SELECT} WHERE i.user_id = %s ORDER BY i.created_at DESC, i.id DESC LIMIT 6", (uid,)
    )
    favorites = db.fetch_all(
        f"{ITEM_SELECT} WHERE i.user_id = %s AND i.is_favorite = 1 ORDER BY i.item_date DESC, i.id DESC LIMIT 6",
        (uid,),
    )
    today = date.today()
    on_this_day = db.fetch_all(
        f"{ITEM_SELECT} WHERE i.user_id = %s AND MONTH(i.item_date) = %s AND DAY(i.item_date) = %s"
        " AND YEAR(i.item_date) < %s ORDER BY i.item_date DESC LIMIT 4",
        (uid, today.month, today.day, today.year),
    )
    attach_tags(recent + favorites + on_this_day)

    return render_template(
        "dashboard.html",
        counts=counts,
        total=total,
        recent=recent,
        favorites=favorites,
        on_this_day=on_this_day,
        collections=user_collections(uid, limit=8),
        greeting=_greeting(datetime.now().hour),
        today_label=f"{today.strftime('%A')}, {today.day} {today.strftime('%B')}",
    )
