"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/ingestion/ingest_country_indicators_imf.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Layer 1 country macro indicators from IMF datasets.
                      Pulls a small set of canonical macro series via the
                      IMF datamapper REST API (publicly accessible, no key
                      required for low volumes). WEO indicators (GDP, debt,
                      inflation, current account, fiscal balance) are
                      typically annual with semi-annual releases (April +
                      October WEO updates).

Cadence             : Quarterly. Cron: 0 6 1 1,4,7,10 * UTC.
Writes to           : cr_country_indicators

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §2.1
                      IMF datamapper:
                      https://www.imf.org/external/datamapper/api/v1/
"""

from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass

import requests
import structlog

from ingestion import _adapter

log = structlog.get_logger()

IMF_BASE = "https://www.imf.org/external/datamapper/api/v1"
COUNTRIES = ["USA", "CHN", "HKG", "AUS"]


@dataclass(frozen=True)
class IMFIndicator:
    indicator_name: str
    imf_code: str            # IMF datamapper indicator code
    dalio_power: str | None
    unit: str

INDICATORS: list[IMFIndicator] = [
    # WEO core
    IMFIndicator("imf_gdp_growth_pct",          "NGDP_RPCH",   "output", "pct"),
    IMFIndicator("imf_gdp_per_capita_usd",      "NGDPDPC",     "output", "usd"),
    IMFIndicator("imf_gov_debt_pct_gdp",        "GGXWDG_NGDP", "cycle",  "pct"),
    IMFIndicator("imf_current_account_pct_gdp", "BCA_NGDPD",   "trade",  "pct"),
    IMFIndicator("imf_inflation_avg_pct",       "PCPIPCH",     "cycle",  "pct"),
    IMFIndicator("imf_fiscal_balance_pct_gdp",  "GGXCNL_NGDP", "cycle",  "pct"),
]


def fetch(indicator_code: str) -> dict:
    """Fetch one indicator across all countries from the IMF datamapper.
    Returns the API's `values.{indicator}.{ISO3}.{year}` nested structure or
    an empty dict on failure.
    """
    url = f"{IMF_BASE}/{indicator_code}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:  # noqa: BLE001
        log.error("imf.fetch_failed", code=indicator_code, error=str(e))
        return {}
    return payload.get("values", {}).get(indicator_code, {})


def run(*, backfill_from_year: int | None = None) -> None:
    end_year = dt.date.today().year + 1   # IMF projections go forward
    start_year = backfill_from_year if backfill_from_year is not None else end_year - 3
    backfill = backfill_from_year is not None

    log.info("imf.run.start",
             start_year=start_year, end_year=end_year,
             indicators=len(INDICATORS), backfill=backfill)

    grand_total = _adapter.UpsertResult()

    with _adapter.connect() as conn:
        for ind in INDICATORS:
            payload = fetch(ind.imf_code)
            if not payload:
                continue

            for country in COUNTRIES:
                series = payload.get(country, {})
                rows = []
                for year_str, value in series.items():
                    try:
                        year = int(year_str)
                    except ValueError:
                        continue
                    if year < start_year or year > end_year:
                        continue
                    if value is None:
                        continue
                    rows.append({
                        "country_code":   country,
                        "indicator_name": ind.indicator_name,
                        "period_end":     dt.date(year, 12, 31),
                        "value":          float(value),
                        "unit":           ind.unit,
                        "dalio_power":    ind.dalio_power,
                        "period_start":   dt.date(year, 1, 1),
                        "event_date":     dt.date(year, 12, 31),
                        "source":         f"imf_datamapper:{ind.imf_code}",
                        "backfill":       backfill,
                        "notes":          None,
                    })

                if not rows:
                    continue
                result = _adapter.upsert_facts(
                    conn,
                    table="cr_country_indicators",
                    rows=rows,
                    business_key_columns=("country_code", "indicator_name", "period_end"),
                    value_columns=("value", "unit", "dalio_power",
                                   "period_start", "event_date"),
                    value_compare_column="value",
                )
                result.log_summary(
                    job="ingest_country_indicators_imf",
                    table=f"cr_country_indicators/{country}/{ind.indicator_name}",
                )
                grand_total.inserted += result.inserted
                grand_total.revised  += result.revised
                grand_total.skipped  += result.skipped
                grand_total.errors.extend(result.errors)

    grand_total.log_summary(job="ingest_country_indicators_imf",
                            table="cr_country_indicators")


if __name__ == "__main__":
    backfill_from_year = None
    if len(sys.argv) > 2 and sys.argv[1] == "--backfill-from-year":
        backfill_from_year = int(sys.argv[2])
    run(backfill_from_year=backfill_from_year)
