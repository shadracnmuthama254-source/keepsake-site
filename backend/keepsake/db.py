"""MySQL access through PyMySQL.

One connection is opened lazily per request and closed when the request ends.
All values are passed as query parameters (never string-formatted into SQL).
"""
from contextlib import contextmanager

import pymysql
from flask import current_app, g
from pymysql.cursors import DictCursor


def connect(cfg, database=True):
    """Open a connection from a config mapping (used by the app and init_db.py)."""
    kwargs = dict(
        host=cfg["DB_HOST"],
        port=cfg["DB_PORT"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
        connect_timeout=10,
    )
    if database:
        kwargs["database"] = cfg["DB_NAME"]
    return pymysql.connect(**kwargs)


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config)
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        try:
            conn.close()  # closing discards any uncommitted work
        except pymysql.MySQLError:
            pass


def fetch_all(sql, args=None):
    with get_db().cursor() as cur:
        cur.execute(sql, args if args else None)
        return list(cur.fetchall())


def fetch_one(sql, args=None):
    with get_db().cursor() as cur:
        cur.execute(sql, args if args else None)
        return cur.fetchone()


def execute(sql, args=None):
    """Run a write statement; returns the affected row count."""
    with get_db().cursor() as cur:
        cur.execute(sql, args if args else None)
        return cur.rowcount


def insert(sql, args=None):
    """Run an INSERT; returns the new row id."""
    with get_db().cursor() as cur:
        cur.execute(sql, args if args else None)
        return cur.lastrowid


@contextmanager
def transaction():
    """Commit on success, roll back if anything inside raises."""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
