"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/ingestion/_adapter.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Shared DB adapter for all catalyst-research ingestion
                      jobs. Provides:
                        - psycopg2 connection as catalyst_research_ingestion
                          via RESEARCH_INGESTION_DATABASE_URL
                        - append-on-revision idempotency: INSERT new, skip
                          unchanged, INSERT new row for revised value
                        - structured logging via structlog
                        - automatic recorded_by stamping with caller's
                          module name (provenance for revision history)
                        - context-manager safe transaction usage

Discipline          : No UPDATE on fact tables. Ever. The ingestion role
                      has INSERT-only on cr_* fact tables; this module
                      enforces the application-level rule that matches.

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §2.2
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import psycopg2
import psycopg2.extras
import structlog
from dotenv import load_dotenv

# Load .env from the project root, falling back to the catalyst-research dir.
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

log = structlog.get_logger()


# -----------------------------------------------------------------------------
# Connection
# -----------------------------------------------------------------------------

def _conn_url() -> str:
    url = os.environ.get("RESEARCH_INGESTION_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "RESEARCH_INGESTION_DATABASE_URL is not set. "
            "Set it in .env on the intl droplet (see .env.template)."
        )
    return url


@contextmanager
def connect():
    """Yield a psycopg2 connection as catalyst_research_ingestion.

    The connection autocommits OFF; commit explicitly. On exception, rollback.
    """
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
# Recorded-by stamping
# -----------------------------------------------------------------------------

def _caller_module() -> str:
    """Walk the call stack to find the first frame outside this file, return
    that frame's module name (e.g. 'ingest_market_prices_daily').

    Used to auto-stamp recorded_by so each ingestion job is attributable.
    """
    frame = sys._getframe(1)
    while frame is not None:
        mod_file = frame.f_globals.get("__file__", "")
        if mod_file and not mod_file.endswith("_adapter.py"):
            name = os.path.splitext(os.path.basename(mod_file))[0]
            return name
        frame = frame.f_back
    return "unknown"


# -----------------------------------------------------------------------------
# Append-on-revision insert
# -----------------------------------------------------------------------------

@dataclass
class UpsertResult:
    inserted: int = 0
    revised: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def log_summary(self, job: str, table: str) -> None:
        log.info(
            "ingest.summary",
            job=job,
            table=table,
            inserted=self.inserted,
            revised=self.revised,
            skipped=self.skipped,
            errors=len(self.errors),
        )


def upsert_fact(
    conn,
    *,
    table: str,
    business_key: Mapping[str, Any],
    value_columns: Mapping[str, Any],
    extra_columns: Mapping[str, Any] | None = None,
    value_compare_column: str = "value",
) -> str:
    """Append-on-revision upsert for a single fact row.

    For each candidate row:
      - If no row matches `business_key`: INSERT (status='inserted').
      - If a row matches and value_compare_column matches the latest: skip.
      - If a row matches but value differs from latest: INSERT new row with
        same business key and fresh recorded_at (status='revised').

    There is NO UPDATE. Revisions append.

    Parameters
    ----------
    conn : psycopg2 connection
    table : target table name (e.g. 'cr_country_indicators')
    business_key : columns that identify a logical fact across revisions
                   (e.g. {'country_code': 'USA', 'indicator_name': 'gdp',
                          'period_end': date(2026,3,31)})
    value_columns : the values being recorded; merged with business_key for
                    the actual INSERT (e.g. {'value': 12.3, 'unit': 'pct'})
    extra_columns : non-key, non-compared columns (e.g. {'source': 'IMF_WEO',
                    'event_date': date(2026,3,31), 'period_start': ...,
                    'backfill': False, 'notes': None})
    value_compare_column : which column in value_columns is the "did it
                           change?" comparator (default 'value').

    Returns
    -------
    'inserted' | 'revised' | 'skipped'
    """
    if value_compare_column not in value_columns:
        raise ValueError(
            f"value_compare_column={value_compare_column!r} not in value_columns"
        )

    extra_columns = dict(extra_columns or {})
    extra_columns.setdefault("recorded_by", _caller_module())

    # Fetch the latest existing value for this business key.
    where_clause = " AND ".join(f"{k} = %s" for k in business_key)
    select_sql = (
        f"SELECT {value_compare_column} FROM {table} "
        f"WHERE {where_clause} "
        f"ORDER BY recorded_at DESC LIMIT 1"
    )
    with conn.cursor() as cur:
        cur.execute(select_sql, tuple(business_key.values()))
        row = cur.fetchone()

    new_value = value_columns[value_compare_column]
    if row is not None:
        existing = row[0]
        if existing == new_value:
            return "skipped"
        status = "revised"
    else:
        status = "inserted"

    all_cols = {**business_key, **value_columns, **extra_columns}
    cols = ", ".join(all_cols.keys())
    placeholders = ", ".join(["%s"] * len(all_cols))
    insert_sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    with conn.cursor() as cur:
        cur.execute(insert_sql, tuple(all_cols.values()))
    return status


def upsert_facts(
    conn,
    *,
    table: str,
    rows: Iterable[Mapping[str, Any]],
    business_key_columns: Sequence[str],
    value_columns: Sequence[str],
    value_compare_column: str = "value",
) -> UpsertResult:
    """Bulk variant of upsert_fact for an iterable of row dicts.

    Each row dict must contain all business_key_columns, all value_columns,
    and any extra columns the table requires. recorded_by is stamped
    automatically.
    """
    result = UpsertResult()
    for row in rows:
        try:
            business_key = {k: row[k] for k in business_key_columns}
            values = {k: row[k] for k in value_columns}
            extras = {
                k: v for k, v in row.items()
                if k not in business_key and k not in values
            }
            status = upsert_fact(
                conn,
                table=table,
                business_key=business_key,
                value_columns=values,
                extra_columns=extras,
                value_compare_column=value_compare_column,
            )
            if status == "inserted":
                result.inserted += 1
            elif status == "revised":
                result.revised += 1
            else:
                result.skipped += 1
        except Exception as e:  # noqa: BLE001
            log.error("ingest.row_failed", table=table, error=str(e), row=row)
            result.errors.append(str(e))
    return result


# -----------------------------------------------------------------------------
# News-style append (different shape — natural dedupe key, not revision)
# -----------------------------------------------------------------------------

def insert_news_event(
    conn,
    *,
    source: str,
    external_id: str | None,
    headline: str,
    event_date,
    body: str | None = None,
    classification: str | None = None,
    raw_payload: dict | None = None,
) -> int | None:
    """Insert one news event idempotently keyed on (source, external_id).

    Returns the new id, or None if the row already existed (dedupe).
    """
    recorded_by = _caller_module()
    sql = (
        "INSERT INTO cr_news_events "
        "(source, external_id, headline, body, event_date, classification, "
        " raw_payload, recorded_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s) "
        "ON CONFLICT (source, external_id) DO NOTHING "
        "RETURNING id"
    )
    payload_json = psycopg2.extras.Json(raw_payload or {})
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (source, external_id, headline, body, event_date,
             classification, payload_json, recorded_by),
        )
        row = cur.fetchone()
        return row[0] if row else None


def link_news_security(conn, *, news_event_id: int, security_id: int) -> None:
    sql = (
        "INSERT INTO cr_news_securities (news_event_id, security_id) "
        "VALUES (%s, %s) ON CONFLICT DO NOTHING"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (news_event_id, security_id))


def link_news_theme(conn, *, news_event_id: int, theme_id: int) -> None:
    sql = (
        "INSERT INTO cr_news_themes (news_event_id, theme_id) "
        "VALUES (%s, %s) ON CONFLICT DO NOTHING"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (news_event_id, theme_id))


# -----------------------------------------------------------------------------
# Reference lookups (security_id, theme_id, etc.)
# -----------------------------------------------------------------------------

def security_id_for_symbol(conn, *, symbol: str, exchange_code: str) -> int | None:
    """Return the existing intl securities.security_id for a given symbol on
    a given exchange, or None if not present. catalyst-research never inserts
    into securities — that is intl's table; we only read.
    """
    sql = (
        "SELECT s.security_id "
        "FROM securities s JOIN exchanges e ON s.exchange_id = e.exchange_id "
        "WHERE s.symbol = %s AND e.code = %s LIMIT 1"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (symbol, exchange_code))
        row = cur.fetchone()
        return row[0] if row else None


def theme_id_for_name(conn, *, name: str) -> int | None:
    sql = "SELECT id FROM themes WHERE name = %s LIMIT 1"
    with conn.cursor() as cur:
        cur.execute(sql, (name,))
        row = cur.fetchone()
        return row[0] if row else None
