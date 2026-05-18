"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/ingestion/ingest_hkex_listing_stats.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Layer 5 — HKEX monthly listing statistics. Tracks IPO
                      counts, IPO funds raised, secondary listings, and
                      Stock Connect monthly flows. Foundational data for
                      Plan 3 (HKEX listing flows as financial-center signal).

Cadence             : Monthly. Cron: 0 9 7 * * UTC.
Writes to           : cr_financial_infra_observations

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §2.1
                      HKEX statistics:
                        - Monthly market highlights:
                          https://www.hkex.com.hk/Market-Data/Statistics/Consolidated-Reports/HKEX-Monthly-Market-Highlights
                        - Stock Connect:
                          https://www.hkex.com.hk/Mutual-Market/Stock-Connect/Statistics-and-Reports

STATUS              : HKEX publishes these as monthly PDF + HTML tables.
                      Format is stable but requires per-page parsing. v1
                      implementation reads from a local pre-staged JSON
                      file (HKEX_STATS_JSON_PATH) — a small downloader can
                      be added in v1.1 once the table parser is verified.
                      The shape and idempotency are correct now.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

import structlog

from ingestion import _adapter

log = structlog.get_logger()

# v1 metric set per architecture Plan 3
METRICS = [
    "ipo_count",
    "ipo_funds_raised_hkd_million",
    "secondary_listings_count",
    "stock_connect_northbound_net_hkd_million",
    "stock_connect_southbound_net_hkd_million",
]


def _load_local_json() -> list[dict]:
    """Load the pre-staged JSON file (one record per month per metric).

    Expected shape:
      [
        {"year": 2026, "month": 4, "metric": "ipo_count", "value": 12},
        {"year": 2026, "month": 4, "metric": "ipo_funds_raised_hkd_million", "value": 4200.5},
        ...
      ]
    """
    path = os.environ.get("HKEX_STATS_JSON_PATH")
    if not path or not os.path.exists(path):
        log.info("hkex_stats.no_source",
                 msg="Set HKEX_STATS_JSON_PATH in .env to ingest HKEX stats.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run(*, backfill: bool = False) -> None:
    items = _load_local_json()
    if not items:
        return

    grand_total = _adapter.UpsertResult()

    with _adapter.connect() as conn:
        rows = []
        for item in items:
            try:
                year = int(item["year"])
                month = int(item["month"])
                metric = str(item["metric"])
                value = float(item["value"])
            except (KeyError, ValueError, TypeError):
                continue
            if metric not in METRICS:
                continue
            period_start = dt.date(year, month, 1)
            period_end = (
                dt.date(year, month + 1, 1) - dt.timedelta(days=1)
                if month < 12
                else dt.date(year, 12, 31)
            )
            rows.append({
                "infra_type":   "hkex_listing",
                "entity_id":    "HKEX",
                "metric_name":  metric,
                "period_end":   period_end,
                "value":        value,
                "unit":         "count" if metric.endswith("count") else
                                ("hkd_million" if "hkd_million" in metric else "value"),
                "period_start": period_start,
                "event_date":   period_end,
                "source":       "hkex_monthly_highlights",
                "backfill":     backfill,
                "metadata":     None,
            })

        if rows:
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

    grand_total.log_summary(job="ingest_hkex_listing_stats",
                            table="cr_financial_infra_observations")


if __name__ == "__main__":
    backfill = "--backfill" in sys.argv
    run(backfill=backfill)
