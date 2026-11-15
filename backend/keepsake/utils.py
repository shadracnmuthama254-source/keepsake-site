"""Small input-cleaning and formatting helpers."""
import re
from datetime import date, datetime
from urllib.parse import urlparse

_CONTROL_ANY = re.compile(r"[\x00-\x1f\x7f]")
_CONTROL_KEEP_NEWLINES = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

MIN_DATE = date(1900, 1, 1)
MAX_DATE = date(2100, 12, 31)


def clean_line(value):
    """Single-line text: control characters removed, whitespace collapsed."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", _CONTROL_ANY.sub(" ", str(value))).strip()


def clean_text(value):
    """Multi-line text: keeps line breaks, removes other control characters."""
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_KEEP_NEWLINES.sub("", text).strip()


def to_int(value):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if 0 < number < 2**31 else None


def parse_date(value):
    """Parse YYYY-MM-DD; returns a date or None."""
    try:
        parsed = datetime.strptime(str(value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None
    return parsed if MIN_DATE <= parsed <= MAX_DATE else None


def escape_like(text):
    """Escape LIKE wildcards so user text is matched literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def normalize_url(value):
    """Return a clean http(s) URL, or None if it is not acceptable."""
    url = clean_line(value)
    if not url or len(url) > 2048 or " " in url:
        return None
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url):
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        return None
    if not parsed.netloc or "." not in parsed.netloc.split("@")[-1] and "localhost" not in parsed.netloc:
        return None
    return url


def domain_of(url):
    if not url:
        return ""
    host = urlparse(url).netloc.split("@")[-1]
    return host[4:] if host.startswith("www.") else host


def normalize_tag(name):
    """Tidy a tag name: no '#', collapsed spaces. Returns '' if unusable."""
    return clean_line(name).lstrip("#").strip()


def human_size(num):
    try:
        size = float(num)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


def file_ext(name):
    if not name or "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()[:5]


def fmt_date(value, long=False):
    if not value:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if long:
        return f"{value.strftime('%A')}, {value.day} {value.strftime('%B %Y')}"
    return f"{value.day} {value.strftime('%b %Y')}"


def fmt_datetime(value):
    if not value:
        return ""
    return f"{value.day} {value.strftime('%b %Y, %H:%M')}"
