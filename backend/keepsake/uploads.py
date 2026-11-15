"""Safe file uploads.

* Only a whitelist of image/document extensions is accepted.
* The file's first bytes ("magic numbers") must match its extension.
* Files are stored outside the web root under random names, in a folder per user.
* Original names are only kept as display text; they never touch the filesystem.
* Files are served through an authenticated route, never as static files.
"""
import os
import re
import uuid
from pathlib import Path

from flask import current_app

# extension -> (mime type, is_image). SVG and HTML are deliberately excluded.
ALLOWED = {
    "jpg": ("image/jpeg", True),
    "jpeg": ("image/jpeg", True),
    "png": ("image/png", True),
    "gif": ("image/gif", True),
    "webp": ("image/webp", True),
    "pdf": ("application/pdf", False),
    "txt": ("text/plain", False),
    "md": ("text/markdown", False),
    "csv": ("text/csv", False),
    "rtf": ("application/rtf", False),
    "doc": ("application/msword", False),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", False),
    "xls": ("application/vnd.ms-excel", False),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", False),
    "ppt": ("application/vnd.ms-powerpoint", False),
    "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", False),
    "odt": ("application/vnd.oasis.opendocument.text", False),
    "ods": ("application/vnd.oasis.opendocument.spreadsheet", False),
    "odp": ("application/vnd.oasis.opendocument.presentation", False),
}

ALLOWED_EXTENSIONS = sorted(ALLOWED)
IMAGE_EXTENSIONS = sorted(e for e, (_, img) in ALLOWED.items() if img)
INLINE_MIMES = {mime for mime, is_image in ALLOWED.values() if is_image}

_ZIP_BASED = {"docx", "xlsx", "pptx", "odt", "ods", "odp"}
_OLE_BASED = {"doc", "xls", "ppt"}
_PLAIN_TEXT = {"txt", "md", "csv"}

STORED_NAME_RE = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{2,5}$")


class UploadError(Exception):
    """A problem with the uploaded file that is safe to show to the user."""


def clean_filename(name):
    """Make a display-safe name (no paths, no control characters)."""
    name = (name or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r'[<>:"|?*]', "_", name).strip().strip(".")
    if len(name) > 150:
        stem, dot, ext = name.rpartition(".")
        name = (stem[:140] + dot + ext) if dot and len(ext) <= 6 else name[:150]
    return name or "file"


def _sniff_ok(ext, head):
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == "gif":
        return head[:6] in (b"GIF87a", b"GIF89a")
    if ext == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == "pdf":
        return b"%PDF-" in head[:1024]
    if ext == "rtf":
        return head.startswith(b"{\\rtf")
    if ext in _ZIP_BASED:
        return head.startswith(b"PK\x03\x04")
    if ext in _OLE_BASED:
        return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if ext in _PLAIN_TEXT:
        return b"\x00" not in head
    return False


def validate_upload(storage, image_only=False):
    """Check name, extension and content signature. Does not write anything."""
    display = clean_filename(storage.filename)
    ext = display.rsplit(".", 1)[-1].lower() if "." in display else ""
    if ext not in ALLOWED:
        raise UploadError(
            "That file type isn't supported. Allowed: " + ", ".join(ALLOWED_EXTENSIONS) + "."
        )
    mime, is_image = ALLOWED[ext]
    if image_only and not is_image:
        raise UploadError("Photos must be an image file (JPG, PNG, GIF or WebP).")
    head = storage.stream.read(2048)
    storage.stream.seek(0)
    if not head:
        raise UploadError("That file is empty.")
    if not _sniff_ok(ext, head):
        raise UploadError(f"That file doesn't look like a genuine .{ext} file.")
    return {"ext": ext, "mime": mime, "is_image": is_image, "original_name": display}


def user_folder(user_id):
    return Path(current_app.config["UPLOAD_FOLDER"]) / str(int(user_id))


def store_upload(storage, user_id, meta):
    """Stream the file to disk under a random name, enforcing the size limit."""
    max_mb = current_app.config["MAX_UPLOAD_MB"]
    max_bytes = max_mb * 1024 * 1024
    folder = user_folder(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(folder, 0o700)
    except OSError:
        pass

    stored_name = f"{uuid.uuid4().hex}.{meta['ext']}"
    final = folder / stored_name
    partial = folder / (stored_name + ".part")
    size = 0
    try:
        with open(partial, "wb") as out:
            while True:
                chunk = storage.stream.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise UploadError(f"That file is larger than the {max_mb} MB limit.")
                out.write(chunk)
        if size == 0:
            raise UploadError("That file is empty.")
        os.replace(partial, final)
        try:
            os.chmod(final, 0o600)
        except OSError:
            pass
    except BaseException:
        try:
            partial.unlink()
        except FileNotFoundError:
            pass
        raise
    return {"stored_name": stored_name, "size": size}


def stored_path(user_id, stored_name):
    """Absolute path for a stored file, or None if the name is not one of ours."""
    if not stored_name or not STORED_NAME_RE.match(stored_name):
        return None
    return user_folder(user_id) / stored_name


def delete_stored_file(user_id, stored_name):
    path = stored_path(user_id, stored_name)
    if path is None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        current_app.logger.warning("Could not delete stored file %s", stored_name)
