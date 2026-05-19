"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/ingestion/ingest_un_comtrade.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Layer 4 bilateral relationships — UN Comtrade monthly
                      bilateral trade flows for the six v1 country pairs.

                      For symmetric measures we store one direction (the
                      alphabetically-first country as `country_a`). The
                      CHECK constraint `country_a < country_b` is enforced
                      by the schema; the loop honours it.

                      For directional flows (exports from A to B vs B to A)
                      we use distinct `dimension` names: `bilateral_exports_a_to_b_usd`
                      and `bilateral_exports_b_to_a_usd`. The alphabetical
                      ordering of country_a/country_b stays the same.

Cadence             : Monthly (data publishes with ~3-month lag).
                      Cron: 0 8 5 * * UTC.
Writes to           : cr_country_pair_observations

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §2.1
                      https://comtradeplus.un.org/

STATUS              : Public API endpoint sketched from current docs. UN_COMTRADE_API_KEY
                      raises the free-tier rate limit; without it the public
                      endpoint allows ~100 calls/day. Six pairs × ~24 months =
                      144 calls for a year of backfill — manageable within
                      free tier with light pacing.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import time
from itertools import combinations

import requests
import structlog

from ingestion import _adapter

log = structlog.get_logger()

COMTRADE_BASE = "https://comtradeapi.un.org/data/v1/get"
COUNTRIES = ["AUS", "CHN", "HKG", "USA"]
ISO_TO_M49 = {"AUS": 36, "CHN": 156, "HKG": 344, "USA": 842}


def _api_key() -> str | None:
    return os.environ.get("UN_COMTRADE_API_KEY")


def fetch_pair_month(*, reporter_iso: str, partner_iso: str,
                     year: int, month: int) -> float | None:
    """Return reporter→partner exports in USD for the given month, or None
    if the API returns no data or the call fails.
    """
    reporter_m49 = ISO_TO_M49[reporter_iso]
    partner_m49  = ISO_TO_M49[partner_iso]

    headers = {}
    if (k := _api_key()):
        headers["Ocp-Apim-Subscription-Key"] = k

    period = f"{year}{month:02d}"
    url = f"{COMTRADE_BASE}/C/M/HS"   # commodities, monthly, HS classification
    params = {
        "reporterCode": reporter_m49,
        "partnerCode":  partner_m49,
        "flowCode":     "X",          # exports
        "period":       period,
        "freqCode":     "M",
        "clCode":       "HS",
        "cmdCode":      "TOTAL",
        "format":       "JSON",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data") or []
    except Exception as e:  # noqa: BLE001
        log.error("comtrade.fetch_failed",
                  reporter=reporter_iso, partner=partner_iso,
                  year=year, month=month, error=str(e))
        return None

    if not data:
        return None
    # primaryValue is USD value
    return float(data[0].get("primaryValue") or 0.0)


def run(*, months_back: int = 4, backfill_from: tuple[int, int] | None = None) -> None:
    """months_back: how many months prior to today to refresh (default 4 to
    handle UN Comtrade's ~3-month lag).
    backfill_from: (year, month) start of backfill window.
    """
    today = dt.date.today()
    if backfill_from is not None:
        start_year, start_month = backfill_from
        backfill = True
    else:
        d = (today.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
        for _ in range(months_back):
            d = (d.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
        start_year, start_month = d.year, d.month
        backfill = False

    log.info("comtrade.run.start",
             start=f"{start_year}-{start_month:02d}",
             end=f"{today.year}-{today.month:02d}", backfill=backfill)

    grand_total = _adapter.UpsertResult()

    with _adapter.connect() as conn:
        for iso_a, iso_b in combinations(sorted(COUNTRIES), 2):
            year, month = start_year, start_month
            while (year, month) <= (today.year, today.month):
                # Two directional pulls per month.
                v_ab = fetch_pair_month(reporter_iso=iso_a,
                                        partner_iso=iso_b,
                                        year=year, month=month)
                v_ba = fetch_pair_month(reporter_iso=iso_b,
                                        partner_iso=iso_a,
                                        year=year, month=month)
                time.sleep(0.4)  # gentle pacing

                period_start = dt.date(year, month, 1)
                period_end = (
                    period_start.replace(month=month + 1) - dt.timedelta(days=1)
                    if month < 12
                    else dt.date(year, 12, 31)
                )

                rows = []
                if v_ab is not None:
                    rows.append({
                        "country_a":    iso_a,
                        "country_b":    iso_b,
                        "dimension":    "bilateral_exports_a_to_b_usd",
                        "period_end":   period_end,
                        "value":        v_ab,
                        "unit":         "usd",
                        "period_start": period_start,
                        "event_date":   period_end,
                        "source":       "un_comtrade",
                        "backfill":     backfill,
                    })
                if v_ba is not None:
                    rows.append({
                        "country_a":    iso_a,
                        "country_b":    iso_b,
                        "dimension":    "bilateral_exports_b_to_a_usd",
                        "period_end":   period_end,
                        "value":        v_ba,
                        "unit":         "usd",
                        "period_start": period_start,
                        "event_date":   period_end,
                        "source":       "un_comtrade",
                        "backfill":     backfill,
                    })

                if rows:
                    result = _adapter.upsert_facts(
                        conn,
                        table="cr_country_pair_observations",
                        rows=rows,
                        business_key_columns=("country_a", "country_b",
                                              "dimension", "period_end"),
                        value_columns=("value", "unit", "period_start", "event_date"),
                        value_compare_column="value",
                    )
                    grand_total.inserted += result.inserted
                    grand_total.revised  += result.revised
                    grand_total.skipped  += result.skipped
                    grand_total.errors.extend(result.errors)

                # Advance one month
                if month == 12:
                    year, month = year + 1, 1
                else:
                    month += 1

    grand_total.log_summary(job="ingest_un_comtrade",
                            table="cr_country_pair_observations")


if __name__ == "__main__":
    backfill_from = None
    args = sys.argv[1:]
    if args and args[0] == "--backfill-from" and len(args) >= 2:
        y, m = args[1].split("-")
        backfill_from = (int(y), int(m))
    run(backfill_from=backfill_from)
