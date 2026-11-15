#!/usr/bin/env python3
"""Create the Keepsake database and tables.

    python init_db.py            create the database (if needed) and all tables
    python init_db.py --reset    DROP every Keepsake table first (asks to confirm)

Connection settings come from your .env file.
"""
import argparse
import re
import sys
from pathlib import Path

import pymysql

from keepsake.config import load_config
from keepsake.db import connect

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"
TABLES_DROP_ORDER = ["item_tags", "items", "tags", "collections", "password_resets", "users"]
ERR_UNKNOWN_DB = 1049


def load_statements():
    lines = [ln for ln in SCHEMA_FILE.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("--")]
    return [stmt.strip() for stmt in "\n".join(lines).split(";") if stmt.strip()]


def open_database(cfg):
    """Connect to the configured database, creating it first if it doesn't exist."""
    name = cfg["DB_NAME"]
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", name):
        sys.exit("DB_NAME may only contain letters, numbers and underscores.")
    try:
        return connect(cfg)
    except pymysql.err.OperationalError as exc:
        if exc.args[0] != ERR_UNKNOWN_DB:
            raise
    print(f"Database '{name}' does not exist yet - creating it...")
    server = connect(cfg, database=False)
    try:
        with server.cursor() as cur:
            cur.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        server.commit()
    finally:
        server.close()
    return connect(cfg)


def explain_connection_error(cfg, exc):
    code = exc.args[0] if exc.args else None
    print(f"\nCould not connect to MySQL at {cfg['DB_HOST']}:{cfg['DB_PORT']} as '{cfg['DB_USER']}'.")
    if code == 1045:
        print("  -> Access denied: check DB_USER and DB_PASSWORD in your .env file.")
    elif code == 1044:
        print("  -> This user is not allowed to use/create that database. Create it as an admin and")
        print(f"     GRANT ALL PRIVILEGES ON `{cfg['DB_NAME']}`.* TO '{cfg['DB_USER']}'@'localhost';")
    elif code == 2003:
        print("  -> The server is not reachable: is MySQL running, and are DB_HOST / DB_PORT correct?")
    else:
        print(f"  -> {exc}")


def main():
    parser = argparse.ArgumentParser(description="Create the Keepsake database tables.")
    parser.add_argument("--reset", action="store_true", help="drop all Keepsake tables first (DELETES ALL DATA)")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt for --reset")
    args = parser.parse_args()

    cfg = load_config()
    try:
        conn = open_database(cfg)
    except pymysql.MySQLError as exc:
        explain_connection_error(cfg, exc)
        return 1

    try:
        with conn.cursor() as cur:
            if args.reset:
                if not args.yes:
                    answer = input(f"This permanently deletes ALL data in '{cfg['DB_NAME']}'. Type 'yes' to continue: ")
                    if answer.strip().lower() != "yes":
                        print("Cancelled - nothing was changed.")
                        return 0
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                for table in TABLES_DROP_ORDER:
                    cur.execute(f"DROP TABLE IF EXISTS `{table}`")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
                print("Dropped existing tables.")
            for statement in load_statements():
                cur.execute(statement)
        conn.commit()
    except pymysql.MySQLError as exc:
        conn.rollback()
        print(f"\nDatabase error while creating tables: {exc}")
        return 1
    finally:
        conn.close()

    print(f"Done! Database '{cfg['DB_NAME']}' is ready. Start the site with:  python app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
