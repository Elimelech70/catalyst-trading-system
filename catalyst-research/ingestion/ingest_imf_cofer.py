"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/ingestion/ingest_imf_cofer.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Layer 5 — IMF COFER (Currency Composition of Official
                      Foreign Exchange Reserves) quarterly time series.
                      Central to Plan 2 (reserve diversification → gold) and
                      one of the most diagnostic Layer-5 signals in Dalio's
                      transition framework.

                      Stores one row per (currency, quarter) under the
                      infra_type 'cofer_reserve_composition', with
                      entity_id = currency code (USD, EUR, JPY, CNY, ...)
                      and metric_name = 'allocated_share_pct'.

Cadence             : Quarterly (~6-month publish lag).
                      Cron: 0 9 5 1,4,7,10 * UTC.
Writes to           : cr_financial_infra_observations

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §2.1
                      https://data.imf.org/cofer
                      Architecture Plan 2.

STATUS              : The IMF data portal serves COFER as downloadable CSV.
                      The exact URL pattern changes; v1 implementation reads
                      from a local CSV path (refreshed quarterly by hand or
                      by a follow-up downloader). The fetch_csv() function
                      below accepts either a local path (COFER_CSV_PATH) or
                      a configured URL (COFER_CSV_URL).
"""

from __future__ import annotations

import csv
import datetime as dt
import os
import sys
from io import StringIO

import requests
import structlog

from ingestion import _adapter

log = structlog.get_logger()

CURRENCIES = ["USD", "EUR", "JPY", "GBP", "CNY", "AUD", "CAD", "CHF"]


def _load_cofer_csv_text() -> str | None:
    path = os.environ.get("COFER_CSV_PATH")
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    url = os.environ.get("COFER_CSV_URL")
    if url:
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return resp.text
        except Exception as e:  # noqa: BLE001
            log.error("cofer.fetch_failed", url=url, error=str(e))
            return None
    log.info("cofer.no_source",
             msg="Set COFER_CSV_PATH or COFER_CSV_URL in .env to ingest COFER.")
    return None


def parse_cofer_csv(text: str) -> list[dict]:
    """Parse the IMF COFER quarterly CSV.

    The COFER CSV format is wide: rows = currency series, columns = quarters
    (e.g. 2024Q1). We pivot it long-form into one row per (currency, quarter).

    The function is intentionally defensive — it tries to detect the period
    columns by regex on the header and skips rows whose first column isn't a
    recognised currency or share-of-total label.
    """
    out: list[dict] = []
    reader = csv.reader(StringIO(text))
    rows = list(reader)
    if not rows:
        return out
    header = rows[0]
    period_cols: list[tuple[int, dt.date]] = []
    for idx, col in enumerate(header):
        col_clean = col.strip()
        if len(col_clean) == 6 and col_clean[4] == "Q" and col_clean[:4].isdigit() \
                and col_clean[5] in "1234":
            year = int(col_clean[:4])
            q = int(col_clean[5])
            quarter_end_month = q * 3
            day = 31 if quarter_end_month in (3, 12) else 30
            try:
                period_end = dt.date(year, quarter_end_month, day)
            except ValueError:
                period_end = dt.date(year, quarter_end_month, 28)
            period_cols.append((idx, period_end))

    if not period_cols:
        log.warning("cofer.no_period_columns_in_header", header=header[:8])
        return out

    for row in rows[1:]:
        if not row:
            continue
        label = row[0].strip().upper()
        # Heuristic: recognise rows whose label starts with a currency code.
        currency = None
        for c in CURRENCIES:
            if label.startswith(c):
                currency = c
                break
        if currency is None:
            continue
        for idx, period_end in period_cols:
            if idx >= len(row):
                continue
            cell = row[idx].strip().replace(",", "")
            if not cell or cell.lower() in ("n/a", "na", "."):
                continue
            try:
                value = float(cell)
            except ValueError:
                continue
            period_start = period_end.replace(day=1)
            # Period start = first day of quarter
            quarter_start_month = ((period_end.month - 1) // 3) * 3 + 1
            period_start = period_start.replace(month=quarter_start_month, day=1)
            out.append({
                "entity_id":     currency,
                "metric_name":   "allocated_share_pct",
                "period_start":  period_start,
                "period_end":    period_end,
                "event_date":    period_end,
                "value":         value,
                "unit":          "pct",
            })
    return out


def run(*, backfill: bool = False) -> None:
    text = _load_cofer_csv_text()
    if not text:
        return

    rows_raw = parse_cofer_csv(text)
    log.info("cofer.parsed_rows", count=len(rows_raw))
    if not rows_raw:
        return

    grand_total = _adapter.UpsertResult()

    with _adapter.connect() as conn:
        rows = []
        for r in rows_raw:
            rows.append({
                "infra_type":   "cofer_reserve_composition",
                "entity_id":    r["entity_id"],
                "metric_name":  r["metric_name"],
                "period_end":   r["period_end"],
                "value":        r["value"],
                "unit":         r["unit"],
                "period_start": r["period_start"],
                "event_date":   r["event_date"],
                "source":       "imf_cofer",
                "backfill":     backfill,
                "metadata":     None,
            })

        result = _adapter.upsert_facts(
            conn,
            table="cr_financial_infra_observations",
            rows=rows,
            business_key_columns=("infra_type", "entity_id",
                                  "metric_name", "period_end"),
            value_columns=("value", "unit", "period_start", "event_date"),
            value_compare_column="value",
        )
        grand_total.inserted += result.inserted
        grand_total.revised  += result.revised
        grand_total.skipped  += result.skipped
        grand_total.errors.extend(result.errors)

    grand_total.log_summary(job="ingest_imf_cofer",
                            table="cr_financial_infra_observations")


if __name__ == "__main__":
    backfill = "--backfill" in sys.argv
    run(backfill=backfill)
