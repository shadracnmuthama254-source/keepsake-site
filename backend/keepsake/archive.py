"""Create, view, edit, delete and favourite archive items; serve uploaded files."""
from datetime import date

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, send_file, url_for,
)

from . import db
from .constants import TYPES
from .queries import (
    fetch_items_page, get_item, has_any_items, is_filtered, parse_filters, user_collections, user_tags,
)
from .security import login_required, safe_next
from .uploads import (
    INLINE_MIMES, UploadError, delete_stored_file, stored_path, store_upload, validate_upload,
)
from .utils import clean_line, clean_text, normalize_tag, normalize_url, parse_date, to_int

bp = Blueprint("archive", __name__, url_prefix="/archive")

MAX_TITLE = 200
MAX_DESCRIPTION = 20000
MAX_LOCATION = 200
MAX_TAG_LEN = 40
MAX_TAGS = 15


# ------------------------------------------------------------------ list
@bp.route("/")
@login_required
def list_items():
    uid = g.user["id"]
    filters = parse_filters(request.args)
    items, total, pages, page = fetch_items_page(uid, filters)
    return render_template(
        "items/list.html",
        items=items,
        total=total,
        pages=pages,
        page=page,
        filters=filters,
        filtered=is_filtered(filters),
        has_any=True if total else has_any_items(uid),
        collections=user_collections(uid),
        tags=user_tags(uid),
    )


# ------------------------------------------------------------------ form helpers
def _parse_tags(raw):
    names, seen, error = [], set(), None
    for part in (raw or "").replace("\n", ",").split(","):
        name = normalize_tag(part)
        if not name or name.lower() in seen:
            continue
        if len(name) > MAX_TAG_LEN:
            error = f"Each tag can be at most {MAX_TAG_LEN} characters."
            continue
        seen.add(name.lower())
        names.append(name)
    if len(names) > MAX_TAGS:
        error = f"Use {MAX_TAGS} tags or fewer."
    return names[:MAX_TAGS], error


def _parse_form(form, uid):
    """Validate the item form. Returns (values_for_redisplay, clean_data, errors)."""
    errors = {}
    item_type = form.get("type", "")
    title = clean_line(form.get("title"))
    description = clean_text(form.get("description"))
    location = clean_line(form.get("location"))
    raw_date = form.get("item_date", "")
    raw_url = form.get("url", "")
    raw_tags = form.get("tags", "")
    raw_collection = form.get("collection_id", "")

    if item_type not in TYPES:
        errors["type"] = "Pick what kind of keepsake this is."
    if not title:
        errors["title"] = "Give it a title."
    elif len(title) > MAX_TITLE:
        errors["title"] = f"Keep the title to {MAX_TITLE} characters or fewer."
    if len(description) > MAX_DESCRIPTION:
        errors["description"] = f"That's too long - please stay under {MAX_DESCRIPTION:,} characters."
    if len(location) > MAX_LOCATION:
        errors["location"] = f"Keep the location to {MAX_LOCATION} characters or fewer."

    item_date = parse_date(raw_date)
    if item_date is None:
        errors["item_date"] = "Choose a valid date."

    collection_id = None
    if raw_collection:
        collection_id = to_int(raw_collection)
        owned = collection_id and db.fetch_one(
            "SELECT id FROM collections WHERE id = %s AND user_id = %s", (collection_id, uid)
        )
        if not owned:
            collection_id = None
            errors["collection_id"] = "That collection doesn't exist."

    url = None
    if item_type == "link":
        url = normalize_url(raw_url)
        if url is None:
            errors["url"] = "Enter a valid web address, e.g. https://example.com"

    tag_names, tag_error = _parse_tags(raw_tags)
    if tag_error:
        errors["tags"] = tag_error

    values = {
        "type": item_type, "title": title, "description": description, "location": location,
        "item_date": raw_date, "url": raw_url, "tags": raw_tags, "collection_id": raw_collection,
        "is_favorite": form.get("is_favorite") == "1",
    }
    data = {
        "type": item_type, "title": title, "description": description or None,
        "location": location or None, "item_date": item_date, "collection_id": collection_id,
        "url": url, "tags": tag_names, "is_favorite": 1 if form.get("is_favorite") == "1" else 0,
    }
    return values, data, errors


def _sync_tags(uid, item_id, names):
    db.execute("DELETE FROM item_tags WHERE item_id = %s", (item_id,))
    for name in names:
        tag_id = db.insert(
            "INSERT INTO tags (user_id, name) VALUES (%s, %s)"
            " ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)",
            (uid, name),
        )
        db.execute("INSERT IGNORE INTO item_tags (item_id, tag_id) VALUES (%s, %s)", (item_id, tag_id))


def _form_page(uid, values, errors, item=None):
    return render_template(
        "items/form.html",
        values=values,
        errors=errors,
        item=item,
        collections=user_collections(uid),
        tags=user_tags(uid),
    )


def _upload_problem(data, upload, existing=None):
    """Check the file rules for the chosen type. Returns (meta, error)."""
    if data["type"] == "link":
        return None, None
    has_upload = bool(upload and upload.filename)
    if has_upload:
        try:
            return validate_upload(upload, image_only=data["type"] == "photo"), None
        except UploadError as exc:
            return None, str(exc)
    if data["type"] == "photo":
        if existing and (existing.get("file_mime") or "").startswith("image/"):
            return None, None
        return None, "Please choose a photo to upload (JPG, PNG, GIF or WebP)."
    if data["type"] == "document" and not (existing and existing.get("file_stored_name")):
        return None, "Please choose a document to upload."
    return None, None


# ------------------------------------------------------------------ create
@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    uid = g.user["id"]
    errors = {}

    if request.method == "POST":
        values, data, errors = _parse_form(request.form, uid)
        upload = request.files.get("file")
        meta = None
        if not errors.get("type"):
            meta, problem = _upload_problem(data, upload)
            if problem:
                errors["file"] = problem

        if not errors:
            saved = None
            try:
                if meta:
                    saved = store_upload(upload, uid, meta)
            except UploadError as exc:
                errors["file"] = str(exc)

            if not errors:
                try:
                    with db.transaction():
                        item_id = db.insert(
                            "INSERT INTO items (user_id, collection_id, type, title, description, url,"
                            " item_date, location, is_favorite, file_stored_name, file_original_name,"
                            " file_mime, file_size)"
                            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (
                                uid, data["collection_id"], data["type"], data["title"], data["description"],
                                data["url"], data["item_date"], data["location"], data["is_favorite"],
                                saved["stored_name"] if saved else None,
                                meta["original_name"] if saved else None,
                                meta["mime"] if saved else None,
                                saved["size"] if saved else None,
                            ),
                        )
                        _sync_tags(uid, item_id, data["tags"])
                except Exception:
                    if saved:
                        delete_stored_file(uid, saved["stored_name"])
                    raise
                flash("Saved to your scrapbook! ✨", "success")
                return redirect(url_for("archive.detail", item_id=item_id))
        return _form_page(uid, values, errors)

    requested = request.args.get("type", "")
    values = {
        "type": requested if requested in TYPES else "memory",
        "title": "", "description": "", "location": "", "url": "", "tags": "",
        "item_date": date.today().isoformat(),
        "collection_id": str(to_int(request.args.get("collection")) or ""),
        "is_favorite": False,
    }
    return _form_page(uid, values, errors)


# ------------------------------------------------------------------ detail
@bp.route("/<int:item_id>")
@login_required
def detail(item_id):
    item = get_item(g.user["id"], item_id)
    if item is None:
        abort(404)
    return render_template("items/detail.html", item=item)


# ------------------------------------------------------------------ edit
@bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit(item_id):
    uid = g.user["id"]
    item = get_item(uid, item_id)
    if item is None:
        abort(404)
    errors = {}

    if request.method == "POST":
        values, data, errors = _parse_form(request.form, uid)
        upload = request.files.get("file")
        remove_file = request.form.get("remove_file") == "1"
        meta = None
        if not errors.get("type"):
            has_upload = bool(upload and upload.filename)
            existing = None if (remove_file and not has_upload) else item
            meta, problem = _upload_problem(data, upload, existing)
            if problem:
                errors["file"] = problem

        if not errors:
            saved = None
            try:
                if meta:
                    saved = store_upload(upload, uid, meta)
            except UploadError as exc:
                errors["file"] = str(exc)

            if not errors:
                file_cols = (
                    item["file_stored_name"], item["file_original_name"], item["file_mime"], item["file_size"]
                )
                old_file = None
                if saved:
                    old_file = item["file_stored_name"]
                    file_cols = (saved["stored_name"], meta["original_name"], meta["mime"], saved["size"])
                elif (remove_file or data["type"] == "link") and item["file_stored_name"]:
                    # Removed on request, or the item became a link (links carry no file).
                    old_file = item["file_stored_name"]
                    file_cols = (None, None, None, None)
                try:
                    with db.transaction():
                        db.execute(
                            "UPDATE items SET collection_id = %s, type = %s, title = %s, description = %s,"
                            " url = %s, item_date = %s, location = %s, is_favorite = %s,"
                            " file_stored_name = %s, file_original_name = %s, file_mime = %s, file_size = %s"
                            " WHERE id = %s AND user_id = %s",
                            (
                                data["collection_id"], data["type"], data["title"], data["description"],
                                data["url"], data["item_date"], data["location"], data["is_favorite"],
                                *file_cols, item_id, uid,
                            ),
                        )
                        _sync_tags(uid, item_id, data["tags"])
                except Exception:
                    if saved:
                        delete_stored_file(uid, saved["stored_name"])
                    raise
                if old_file:
                    delete_stored_file(uid, old_file)
                flash("Your changes are saved. ✨", "success")
                return redirect(url_for("archive.detail", item_id=item_id))
        return _form_page(uid, values, errors, item)

    values = {
        "type": item["type"], "title": item["title"], "description": item["description"] or "",
        "location": item["location"] or "", "url": item["url"] or "",
        "tags": ", ".join(t["name"] for t in item["tags"]),
        "item_date": item["item_date"].isoformat(),
        "collection_id": str(item["collection_id"] or ""),
        "is_favorite": bool(item["is_favorite"]),
    }
    return _form_page(uid, values, errors, item)


# ------------------------------------------------------------------ delete / favourite
@bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete(item_id):
    uid = g.user["id"]
    item = db.fetch_one(
        "SELECT id, title, file_stored_name FROM items WHERE id = %s AND user_id = %s", (item_id, uid)
    )
    if item is None:
        abort(404)
    with db.transaction():
        db.execute("DELETE FROM items WHERE id = %s AND user_id = %s", (item_id, uid))
    if item["file_stored_name"]:
        delete_stored_file(uid, item["file_stored_name"])
    flash(f"“{item['title']}” was deleted.", "success")
    return redirect(url_for("archive.list_items"))


@bp.route("/<int:item_id>/favorite", methods=["POST"])
@login_required
def toggle_favorite(item_id):
    uid = g.user["id"]
    with db.transaction():
        changed = db.execute(
            "UPDATE items SET is_favorite = 1 - is_favorite, updated_at = updated_at"
            " WHERE id = %s AND user_id = %s",
            (item_id, uid),
        )
    if not changed:
        abort(404)
    row = db.fetch_one("SELECT is_favorite FROM items WHERE id = %s AND user_id = %s", (item_id, uid))
    flash("Added to your favorites ♥" if row["is_favorite"] else "Removed from favorites.", "success")
    return redirect(safe_next(request.form.get("next"), url_for("archive.detail", item_id=item_id)))


# ------------------------------------------------------------------ files
def _send(item_id, force_download):
    uid = g.user["id"]
    item = db.fetch_one(
        "SELECT file_stored_name, file_original_name, file_mime FROM items WHERE id = %s AND user_id = %s",
        (item_id, uid),
    )
    if not item or not item["file_stored_name"]:
        abort(404)
    path = stored_path(uid, item["file_stored_name"])
    if path is None or not path.is_file():
        abort(404)
    inline = item["file_mime"] in INLINE_MIMES and not force_download
    response = send_file(
        path,
        mimetype=item["file_mime"] or "application/octet-stream",
        as_attachment=not inline,
        download_name=item["file_original_name"] or "download",
        conditional=True,
        max_age=0,
    )
    response.headers["Cache-Control"] = "private, max-age=600"
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    return response


@bp.route("/<int:item_id>/file")
@login_required
def file_view(item_id):
    return _send(item_id, force_download=False)


@bp.route("/<int:item_id>/download")
@login_required
def file_download(item_id):
    return _send(item_id, force_download=True)
