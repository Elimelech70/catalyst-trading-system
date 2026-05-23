"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/tests/test_adapter_idempotency.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Tests for ingestion._adapter — the append-on-revision
                      idempotency primitive. These tests use an in-memory
                      mock connection so they run in CI without a real
                      PostgreSQL. The real DB integration test is the Phase
                      1.4 smoke query in 001_initial_schema.sql.

                      pytest -q catalyst-research/tests/test_adapter_idempotency.py
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

# Allow the tests to import without a real DB URL set.
import os
os.environ.setdefault("RESEARCH_INGESTION_DATABASE_URL", "postgres://test:test@localhost/test")

from ingestion import _adapter


# -----------------------------------------------------------------------------
# Minimal mock connection
# -----------------------------------------------------------------------------

class _MockCursor:
    def __init__(self, store: dict):
        self.store = store
        self._last_result: list[Any] | None = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql: str, params: tuple = ()):
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT"):
            # Heuristic: SELECT value FROM table WHERE ... ORDER BY recorded_at DESC LIMIT 1
            # We only need to return the latest existing value for the key.
            table = sql.split("FROM", 1)[1].split()[0]
            key_values = params  # the WHERE params, in order of keys (preserves dict order)
            rows = self.store.get(table, [])
            # Find latest matching row
            for row in reversed(rows):
                row_key_subset = tuple(row.get(k) for k in self.store["_keys"][table])
                if row_key_subset == key_values:
                    self._last_result = [row[self.store["_value_col"][table]]]
                    return
            self._last_result = None
        elif sql_upper.startswith("INSERT"):
            # Extract table and column list naively from "INSERT INTO TABLE (cols) VALUES (..)"
            after_into = sql.split("INTO", 1)[1].strip()
            table = after_into.split("(", 1)[0].strip()
            cols_str = after_into.split("(", 1)[1].split(")", 1)[0]
            cols = [c.strip() for c in cols_str.split(",")]
            row = dict(zip(cols, params))
            row.setdefault("recorded_at", dt.datetime.now())
            self.store.setdefault(table, []).append(row)
            self._last_result = None
        else:
            self._last_result = None

    def fetchone(self):
        if self._last_result is None:
            return None
        return tuple(self._last_result)


class _MockConn:
    def __init__(self, *, keys: dict, value_col: dict):
        self.store = {"_keys": keys, "_value_col": value_col}

    def cursor(self, *args, **kwargs):
        return _MockCursor(self.store)


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def _make_conn():
    return _MockConn(
        keys={"cr_country_indicators": ("country_code", "indicator_name", "period_end")},
        value_col={"cr_country_indicators": "value"},
    )


def _bk():
    return {
        "country_code": "USA",
        "indicator_name": "gdp_growth_pct",
        "period_end": dt.date(2026, 3, 31),
    }


def test_first_insert_is_inserted():
    conn = _make_conn()
    status = _adapter.upsert_fact(
        conn,
        table="cr_country_indicators",
        business_key=_bk(),
        value_columns={"value": 2.5, "unit": "pct"},
        extra_columns={"source": "test", "event_date": dt.date(2026, 3, 31),
                       "period_start": dt.date(2026, 1, 1), "backfill": False},
    )
    assert status == "inserted"
    assert len(conn.store["cr_country_indicators"]) == 1


def test_identical_rerun_is_skipped():
    conn = _make_conn()
    _adapter.upsert_fact(
        conn, table="cr_country_indicators",
        business_key=_bk(),
        value_columns={"value": 2.5, "unit": "pct"},
        extra_columns={"source": "test", "event_date": dt.date(2026, 3, 31),
                       "period_start": dt.date(2026, 1, 1), "backfill": False},
    )
    status = _adapter.upsert_fact(
        conn, table="cr_country_indicators",
        business_key=_bk(),
        value_columns={"value": 2.5, "unit": "pct"},
        extra_columns={"source": "test", "event_date": dt.date(2026, 3, 31),
                       "period_start": dt.date(2026, 1, 1), "backfill": False},
    )
    assert status == "skipped"
    assert len(conn.store["cr_country_indicators"]) == 1


def test_changed_value_appends_revision():
    conn = _make_conn()
    _adapter.upsert_fact(
        conn, table="cr_country_indicators",
        business_key=_bk(),
        value_columns={"value": 2.5, "unit": "pct"},
        extra_columns={"source": "test", "event_date": dt.date(2026, 3, 31),
                       "period_start": dt.date(2026, 1, 1), "backfill": False},
    )
    status = _adapter.upsert_fact(
        conn, table="cr_country_indicators",
        business_key=_bk(),
        value_columns={"value": 2.7, "unit": "pct"},
        extra_columns={"source": "test", "event_date": dt.date(2026, 3, 31),
                       "period_start": dt.date(2026, 1, 1), "backfill": False},
    )
    assert status == "revised"
    assert len(conn.store["cr_country_indicators"]) == 2
    # Latest row has the new value
    assert conn.store["cr_country_indicators"][-1]["value"] == 2.7


def test_recorded_by_is_auto_stamped():
    conn = _make_conn()
    _adapter.upsert_fact(
        conn, table="cr_country_indicators",
        business_key=_bk(),
        value_columns={"value": 2.5, "unit": "pct"},
        extra_columns={"source": "test", "event_date": dt.date(2026, 3, 31),
                       "period_start": dt.date(2026, 1, 1), "backfill": False},
    )
    row = conn.store["cr_country_indicators"][0]
    # _adapter._caller_module() walks the stack — in this test it should
    # find this test file's module name.
    assert "test_adapter_idempotency" in row["recorded_by"]


def test_missing_value_compare_column_raises():
    conn = _make_conn()
    with pytest.raises(ValueError, match="value_compare_column"):
        _adapter.upsert_fact(
            conn, table="cr_country_indicators",
            business_key=_bk(),
            value_columns={"unit": "pct"},  # no 'value' key
            extra_columns={"source": "test"},
        )
