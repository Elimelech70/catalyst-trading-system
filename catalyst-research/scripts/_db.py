"""
Small read-only DB helper for the inspection scripts. Connects via
RESEARCH_ARCHETYPE_DATABASE_URL (broad SELECT, but no write to anything
fact-table-shaped — perfect for reporting).
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


@contextmanager
def connect():
    url = os.environ.get("RESEARCH_ARCHETYPE_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "RESEARCH_ARCHETYPE_DATABASE_URL is not set."
        )
    conn = psycopg2.connect(url)
    try:
        yield conn
    finally:
        conn.close()


def dictrows(conn, sql: str, params: tuple = ()):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())
