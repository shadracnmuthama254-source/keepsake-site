"""Reusable SQL queries for items, collections and tags.

Every query is scoped by user_id so one person can never read another's data.
The only strings interpolated into SQL are fixed fragments defined in this
file (column lists, ORDER BY clauses from a whitelist, placeholder lists).
"""
from math import ceil

from . import db
from .constants import PER_PAGE, SORTS, TYPES
from .utils import clean_line, escape_like, parse_date, to_int

ITEM_SELECT = """
SELECT i.id, i.type, i.title, i.description, i.url, i.item_date, i.location,
       i.is_favorite, i.collection_id,
       i.file_stored_name, i.file_original_name, i.file_mime, i.file_size,
       i.created_at, i.updated_at,
       c.name AS collection_name, c.color AS collection_color, c.emoji AS collection_emoji
FROM items i
LEFT JOIN collections c ON c.id = i.collection_id
"""


# ------------------------------------------------------------------ filters
def parse_filters(args):
    """Turn query-string arguments into a validated filter dict."""
    collection = args.get("collection", "")
    sort = args.get("sort", "date_desc")
    item_type = args.get("type", "")
    return {
        "q": clean_line(args.get("q"))[:100],
        "type": item_type if item_type in TYPES else "",
        "tag": to_int(args.get("tag")),
        "collection": "none" if collection == "none" else to_int(collection),
        "fav": args.get("fav") == "1",
        "date_from": parse_date(args.get("date_from")),
        "date_to": parse_date(args.get("date_to")),
        "sort": sort if sort in SORTS else "date_desc",
        "page": to_int(args.get("page")) or 1,
    }


def is_filtered(f):
    return bool(
        f["q"] or f["type"] or f["tag"] or f["collection"] or f["fav"] or f["date_from"] or f["date_to"]
    )


def _build_where(user_id, f):
    where = ["i.user_id = %s"]
    args = [user_id]

    for term in f["q"].split()[:6]:
        like = f"%{escape_like(term)}%"
        where.append(
            "(i.title LIKE %s OR i.description LIKE %s OR i.location LIKE %s OR i.url LIKE %s"
            " OR i.file_original_name LIKE %s OR EXISTS ("
            "SELECT 1 FROM item_tags it JOIN tags t ON t.id = it.tag_id"
            " WHERE it.item_id = i.id AND t.name LIKE %s))"
        )
        args.extend([like] * 6)

    if f["type"]:
        where.append("i.type = %s")
        args.append(f["type"])
    if f["tag"]:
        where.append("EXISTS (SELECT 1 FROM item_tags it WHERE it.item_id = i.id AND it.tag_id = %s)")
        args.append(f["tag"])
    if f["collection"] == "none":
        where.append("i.collection_id IS NULL")
    elif f["collection"]:
        where.append("i.collection_id = %s")
        args.append(f["collection"])
    if f["fav"]:
        where.append("i.is_favorite = 1")
    if f["date_from"]:
        where.append("i.item_date >= %s")
        args.append(f["date_from"])
    if f["date_to"]:
        where.append("i.item_date <= %s")
        args.append(f["date_to"])
    return " AND ".join(where), args


def fetch_items_page(user_id, f):
    """Return (items, total, pages, page) for the given filters."""
    where, args = _build_where(user_id, f)
    total = db.fetch_one(f"SELECT COUNT(*) AS n FROM items i WHERE {where}", args)["n"]
    pages = max(1, ceil(total / PER_PAGE))
    page = min(max(f["page"], 1), pages)
    order_by = SORTS[f["sort"]][1]  # whitelisted constant
    rows = db.fetch_all(
        f"{ITEM_SELECT} WHERE {where} ORDER BY {order_by} LIMIT %s OFFSET %s",
        args + [PER_PAGE, (page - 1) * PER_PAGE],
    )
    attach_tags(rows)
    return rows, total, pages, page


# ------------------------------------------------------------------ items
def attach_tags(rows):
    """Add a 'tags' list ({id, name}) to each item row, using one query."""
    by_id = {}
    for row in rows:
        row["tags"] = []
        by_id.setdefault(row["id"], []).append(row)
    if not by_id:
        return rows
    placeholders = ",".join(["%s"] * len(by_id))
    tag_rows = db.fetch_all(
        "SELECT it.item_id, t.id, t.name FROM item_tags it JOIN tags t ON t.id = it.tag_id"
        f" WHERE it.item_id IN ({placeholders}) ORDER BY t.name",
        list(by_id),
    )
    for tag in tag_rows:
        for row in by_id[tag["item_id"]]:
            row["tags"].append({"id": tag["id"], "name": tag["name"]})
    return rows


def get_item(user_id, item_id):
    row = db.fetch_one(f"{ITEM_SELECT} WHERE i.user_id = %s AND i.id = %s", (user_id, item_id))
    if row:
        attach_tags([row])
    return row


def has_any_items(user_id):
    return db.fetch_one("SELECT 1 AS x FROM items WHERE user_id = %s LIMIT 1", (user_id,)) is not None


# ------------------------------------------------------------------ collections & tags
def user_collections(user_id, limit=None):
    sql = (
        "SELECT c.id, c.name, c.description, c.color, c.emoji,"
        " (SELECT COUNT(*) FROM items i WHERE i.collection_id = c.id) AS item_count"
        " FROM collections c WHERE c.user_id = %s ORDER BY c.name"
    )
    args = [user_id]
    if limit:
        sql += " LIMIT %s"
        args.append(int(limit))
    return db.fetch_all(sql, args)


def user_tags(user_id):
    return db.fetch_all(
        "SELECT t.id, t.name,"
        " (SELECT COUNT(*) FROM item_tags it WHERE it.tag_id = t.id) AS item_count"
        " FROM tags t WHERE t.user_id = %s ORDER BY t.name",
        (user_id,),
    )
