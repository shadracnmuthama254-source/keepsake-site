"""Collections and tags."""
import pymysql
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from . import db
from .constants import COLLECTION_EMOJIS, COLLECTION_TONES
from .queries import fetch_items_page, parse_filters, user_collections, user_tags
from .security import login_required
from .utils import clean_line, normalize_tag

bp = Blueprint("organize", __name__)

MAX_COLLECTION_NAME = 80
MAX_COLLECTION_DESC = 500
MAX_TAG_LEN = 40


# ================================================================== collections
def _parse_collection_form(form, uid, exclude_id=None):
    name = clean_line(form.get("name"))
    description = clean_line(form.get("description"))
    color = form.get("color", "")
    emoji = form.get("emoji", "")
    errors = {}

    if not name:
        errors["name"] = "Give your collection a name."
    elif len(name) > MAX_COLLECTION_NAME:
        errors["name"] = f"Keep the name to {MAX_COLLECTION_NAME} characters or fewer."
    else:
        sql = "SELECT id FROM collections WHERE user_id = %s AND name = %s"
        args = [uid, name]
        if exclude_id:
            sql += " AND id <> %s"
            args.append(exclude_id)
        if db.fetch_one(sql, args):
            errors["name"] = "You already have a collection with that name."
    if len(description) > MAX_COLLECTION_DESC:
        errors["description"] = f"Keep the description to {MAX_COLLECTION_DESC} characters or fewer."
    if color not in COLLECTION_TONES:
        color = COLLECTION_TONES[0]
    if emoji not in COLLECTION_EMOJIS:
        emoji = COLLECTION_EMOJIS[0]

    values = {"name": name, "description": description, "color": color, "emoji": emoji}
    return values, errors


@bp.route("/collections")
@login_required
def collections():
    return render_template("collections/list.html", collections=user_collections(g.user["id"]))


@bp.route("/collections/new", methods=["GET", "POST"])
@login_required
def collection_new():
    uid = g.user["id"]
    errors = {}
    values = {"name": "", "description": "", "color": COLLECTION_TONES[0], "emoji": COLLECTION_EMOJIS[0]}
    if request.method == "POST":
        values, errors = _parse_collection_form(request.form, uid)
        if not errors:
            try:
                with db.transaction():
                    cid = db.insert(
                        "INSERT INTO collections (user_id, name, description, color, emoji)"
                        " VALUES (%s, %s, %s, %s, %s)",
                        (uid, values["name"], values["description"] or None, values["color"], values["emoji"]),
                    )
            except pymysql.err.IntegrityError:
                errors["name"] = "You already have a collection with that name."
            else:
                flash("Collection created! Now fill it with keepsakes.", "success")
                return redirect(url_for("organize.collection_detail", cid=cid))
    return render_template("collections/form.html", values=values, errors=errors, collection=None)


@bp.route("/collections/<int:cid>")
@login_required
def collection_detail(cid):
    uid = g.user["id"]
    collection = db.fetch_one(
        "SELECT id, name, description, color, emoji, created_at FROM collections WHERE id = %s AND user_id = %s",
        (cid, uid),
    )
    if collection is None:
        abort(404)
    filters = parse_filters(request.args)
    filters["collection"] = cid
    items, total, pages, page = fetch_items_page(uid, filters)
    return render_template(
        "collections/detail.html",
        collection=collection, items=items, total=total, pages=pages, page=page, filters=filters,
    )


@bp.route("/collections/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def collection_edit(cid):
    uid = g.user["id"]
    collection = db.fetch_one(
        "SELECT id, name, description, color, emoji FROM collections WHERE id = %s AND user_id = %s", (cid, uid)
    )
    if collection is None:
        abort(404)
    errors = {}
    values = {
        "name": collection["name"], "description": collection["description"] or "",
        "color": collection["color"], "emoji": collection["emoji"],
    }
    if request.method == "POST":
        values, errors = _parse_collection_form(request.form, uid, exclude_id=cid)
        if not errors:
            try:
                with db.transaction():
                    db.execute(
                        "UPDATE collections SET name = %s, description = %s, color = %s, emoji = %s"
                        " WHERE id = %s AND user_id = %s",
                        (values["name"], values["description"] or None, values["color"], values["emoji"], cid, uid),
                    )
            except pymysql.err.IntegrityError:
                errors["name"] = "You already have a collection with that name."
            else:
                flash("Collection updated.", "success")
                return redirect(url_for("organize.collection_detail", cid=cid))
    return render_template("collections/form.html", values=values, errors=errors, collection=collection)


@bp.route("/collections/<int:cid>/delete", methods=["POST"])
@login_required
def collection_delete(cid):
    uid = g.user["id"]
    collection = db.fetch_one("SELECT name FROM collections WHERE id = %s AND user_id = %s", (cid, uid))
    if collection is None:
        abort(404)
    with db.transaction():
        db.execute("DELETE FROM collections WHERE id = %s AND user_id = %s", (cid, uid))
    flash(f"Collection “{collection['name']}” was deleted. Its items are still in your archive.", "success")
    return redirect(url_for("organize.collections"))


# ================================================================== tags
@bp.route("/tags")
@login_required
def tags():
    return render_template("tags/list.html", tags=user_tags(g.user["id"]))


def _tag_name_problem(name, uid, exclude_id=None):
    if not name:
        return "Type a tag name first."
    if len(name) > MAX_TAG_LEN:
        return f"Tags can be at most {MAX_TAG_LEN} characters."
    sql = "SELECT id FROM tags WHERE user_id = %s AND name = %s"
    args = [uid, name]
    if exclude_id:
        sql += " AND id <> %s"
        args.append(exclude_id)
    if db.fetch_one(sql, args):
        return f"You already have a tag called “{name}”."
    return None


@bp.route("/tags/new", methods=["POST"])
@login_required
def tag_create():
    uid = g.user["id"]
    name = normalize_tag(request.form.get("name"))
    problem = _tag_name_problem(name, uid)
    if problem:
        flash(problem, "error")
    else:
        try:
            with db.transaction():
                db.insert("INSERT INTO tags (user_id, name) VALUES (%s, %s)", (uid, name))
            flash(f"Tag #{name} created.", "success")
        except pymysql.err.IntegrityError:
            flash(f"You already have a tag called “{name}”.", "error")
    return redirect(url_for("organize.tags"))


@bp.route("/tags/<int:tag_id>/rename", methods=["POST"])
@login_required
def tag_rename(tag_id):
    uid = g.user["id"]
    if not db.fetch_one("SELECT id FROM tags WHERE id = %s AND user_id = %s", (tag_id, uid)):
        abort(404)
    name = normalize_tag(request.form.get("name"))
    problem = _tag_name_problem(name, uid, exclude_id=tag_id)
    if problem:
        flash(problem, "error")
    else:
        try:
            with db.transaction():
                db.execute("UPDATE tags SET name = %s WHERE id = %s AND user_id = %s", (name, tag_id, uid))
            flash(f"Tag renamed to #{name}.", "success")
        except pymysql.err.IntegrityError:
            flash(f"You already have a tag called “{name}”.", "error")
    return redirect(url_for("organize.tags"))


@bp.route("/tags/<int:tag_id>/delete", methods=["POST"])
@login_required
def tag_delete(tag_id):
    uid = g.user["id"]
    tag = db.fetch_one("SELECT name FROM tags WHERE id = %s AND user_id = %s", (tag_id, uid))
    if tag is None:
        abort(404)
    with db.transaction():
        db.execute("DELETE FROM tags WHERE id = %s AND user_id = %s", (tag_id, uid))
    flash(f"Tag #{tag['name']} was deleted. Your items are untouched.", "success")
    return redirect(url_for("organize.tags"))
