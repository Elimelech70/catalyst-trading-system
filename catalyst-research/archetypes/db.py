"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/archetypes/db.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Read-only DB adapter used by archetype runs and by the
                      wrapper to write analysis/peer-review/proposal rows.
                      Connects as RESEARCH_ARCHETYPE_DATABASE_URL — SELECT on
                      everything (including intl trading tables, so archetypes
                      learn from real trade outcomes), INSERT only on the
                      three archetype tables.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _conn_url() -> str:
    url = os.environ.get("RESEARCH_ARCHETYPE_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "RESEARCH_ARCHETYPE_DATABASE_URL is not set. "
            "Set it in .env on the intl droplet."
        )
    return url


@contextmanager
def connect():
    conn = psycopg2.connect(_conn_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# READ — context for the next archetype run
# -----------------------------------------------------------------------------

def recent_country_indicators(conn, *, period_start: dt.date,
                              period_end: dt.date) -> list[dict]:
    sql = (
        "SELECT country_code, indicator_name, value, unit, period_end, source "
        "FROM cr_country_indicators "
        "WHERE event_date >= %s AND event_date <= %s "
        "ORDER BY country_code, indicator_name, period_end DESC, recorded_at DESC"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (period_start, period_end))
        return list(cur.fetchall())


def recent_market_prices(conn, *, period_start: dt.date,
                         period_end: dt.date) -> list[dict]:
    sql = (
        "SELECT series_id, series_type, trade_date, close, volume "
        "FROM cr_market_prices "
        "WHERE trade_date >= %s AND trade_date <= %s "
        "ORDER BY series_id, trade_date"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (period_start, period_end))
        return list(cur.fetchall())


def recent_news(conn, *, period_start: dt.date,
                period_end: dt.date, limit: int = 100) -> list[dict]:
    sql = (
        "SELECT id, source, headline, event_date, classification "
        "FROM cr_news_events "
        "WHERE event_date >= %s AND event_date <= %s "
        "ORDER BY event_date DESC LIMIT %s"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (period_start, period_end, limit))
        return list(cur.fetchall())


def active_learning_plans(conn) -> list[dict]:
    sql = (
        "SELECT id, name, question, period_start, period_end, "
        "       expected_observations, null_hypothesis, status "
        "FROM cr_learning_plans "
        "WHERE status IN ('active', 'under_review') "
        "ORDER BY period_end"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def prior_archetype_analyses(conn, *, archetype: str | None = None,
                             since: dt.date | None = None,
                             limit: int = 20) -> list[dict]:
    where = []
    params: list = []
    if archetype:
        where.append("archetype = %s")
        params.append(archetype)
    if since:
        where.append("run_date >= %s")
        params.append(since)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = (
        f"SELECT id, archetype, run_date, scope, conclusions, uncertainties "
        f"FROM cr_archetype_analyses {where_sql} "
        f"ORDER BY run_date DESC, recorded_at DESC LIMIT %s"
    )
    params.append(limit)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, tuple(params))
        return list(cur.fetchall())


# -----------------------------------------------------------------------------
# WRITE — archetype outputs
# -----------------------------------------------------------------------------

def insert_archetype_analysis(conn, *, archetype: str, run_date: dt.date,
                              period_start: dt.date, period_end: dt.date,
                              scope: str, conclusions: str,
                              uncertainties: str | None,
                              supporting_observations: dict | None) -> int:
    sql = (
        "INSERT INTO cr_archetype_analyses "
        "(archetype, run_date, period_start, period_end, scope, "
        " conclusions, uncertainties, supporting_observations) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
        "RETURNING id"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (
            archetype, run_date, period_start, period_end, scope,
            conclusions, uncertainties,
            psycopg2.extras.Json(supporting_observations or {}),
        ))
        return cur.fetchone()[0]


def insert_archetype_peer_review(conn, *, reviewer_archetype: str,
                                 reviewed_analysis_id: int,
                                 agreement: str, critique: str) -> int:
    sql = (
        "INSERT INTO cr_archetype_peer_reviews "
        "(reviewer_archetype, reviewed_analysis_id, agreement, critique) "
        "VALUES (%s, %s, %s, %s) RETURNING id"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (reviewer_archetype, reviewed_analysis_id,
                          agreement, critique))
        return cur.fetchone()[0]


def insert_model_proposal(conn, *, proposing_archetype: str,
                          pattern_description: str,
                          data_series: dict,
                          model_structure: str,
                          success_criteria: str,
                          risks: str | None) -> int:
    sql = (
        "INSERT INTO cr_model_proposals "
        "(proposing_archetype, pattern_description, data_series, "
        " model_structure, success_criteria, risks) "
        "VALUES (%s, %s, %s::jsonb, %s, %s, %s) RETURNING id"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (proposing_archetype, pattern_description,
                          psycopg2.extras.Json(data_series),
                          model_structure, success_criteria, risks))
        return cur.fetchone()[0]
