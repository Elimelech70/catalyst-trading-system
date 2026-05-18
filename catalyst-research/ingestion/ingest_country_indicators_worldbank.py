"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/ingestion/ingest_country_indicators_worldbank.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Layer 1 country macro indicators from the World Bank
                      Indicators API. Broad country coverage, clean REST,
                      no key required. Annual cadence for most series; some
                      quarterly. We pull annual here and let national-source
                      jobs fill in quarterly where useful.

                      Each indicator is mapped to its World Bank code and to
                      a Dalio power dimension (or 'cycle' or NULL).

Cadence             : Quarterly. Cron: 0 7 1 1,4,7,10 * UTC.
Writes to           : cr_country_indicators

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §2.1
                      Architecture §8 ("Indicators per Country — Approximately Eight")
"""

from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass

import requests
import structlog

from ingestion import _adapter

log = structlog.get_logger()

WB_BASE = "https://api.worldbank.org/v2"
COUNTRIES = ["USA", "CHN", "HKG", "AUS"]


@dataclass(frozen=True)
class WBIndicator:
    indicator_name: str    # local canonical name stored in cr_country_indicators.indicator_name
    wb_code: str           # World Bank indicator code
    dalio_power: str | None
    unit: str

# Starter set per architecture §8 — GDP growth, debt/GDP, current account,
# currency strength (proxied via REER), military spending as % of GDP,
# R&D as % of GDP (innovation), tertiary enrollment (education),
# wealth gap proxy (income share of richest 10%).
INDICATORS: list[WBIndicator] = [
    WBIndicator("gdp_growth_pct",            "NY.GDP.MKTP.KD.ZG",   "output",          "pct"),
    WBIndicator("debt_to_gdp_pct",           "GC.DOD.TOTL.GD.ZS",   "cycle",           "pct"),
    WBIndicator("current_account_pct_gdp",   "BN.CAB.XOKA.GD.ZS",   "trade",           "pct"),
    WBIndicator("reer_index",                "PX.REX.REER",         "trade",           "index_score"),
    WBIndicator("military_spending_pct_gdp", "MS.MIL.XPND.GD.ZS",   "military",        "pct"),
    WBIndicator("rd_spending_pct_gdp",       "GB.XPD.RSDV.GD.ZS",   "innovation",      "pct"),
    WBIndicator("tertiary_enrollment_pct",   "SE.TER.ENRR",         "education",       "pct"),
    WBIndicator("income_share_top10_pct",    "SI.DST.10TH.10",      "cycle",           "pct"),
]


def fetch(country: str, wb_code: str, *,
          start_year: int, end_year: int) -> list[dict]:
    """Fetch one indicator/country series. Returns a list of dicts with
    keys year (int), value (float or None), date (date — period end Dec 31).
    Empty list if the call fails.
    """
    url = f"{WB_BASE}/country/{country}/indicator/{wb_code}"
    params = {
        "date":   f"{start_year}:{end_year}",
        "format": "json",
        "per_page": 1000,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:  # noqa: BLE001
        log.error("worldbank.fetch_failed",
                  country=country, code=wb_code, error=str(e))
        return []

    # WB API returns [meta_dict, data_list] when successful, [meta_dict] when
    # the indicator/country combo has no data.
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        return []

    out = []
    for entry in payload[1]:
        try:
            year = int(entry["date"])
        except (TypeError, ValueError, KeyError):
            continue
        value = entry.get("value")
        if value is None:
            continue
        out.append({
            "year": year,
            "value": float(value),
            "period_start": dt.date(year, 1, 1),
            "period_end":   dt.date(year, 12, 31),
            "event_date":   dt.date(year, 12, 31),
        })
    return out


def run(*, backfill_from_year: int | None = None) -> None:
    end_year = dt.date.today().year
    start_year = backfill_from_year if backfill_from_year is not None else end_year - 2
    backfill = backfill_from_year is not None

    log.info("worldbank.run.start",
             start_year=start_year, end_year=end_year,
             indicators=len(INDICATORS), countries=len(COUNTRIES),
             backfill=backfill)

    grand_total = _adapter.UpsertResult()

    with _adapter.connect() as conn:
        for country in COUNTRIES:
            for ind in INDICATORS:
                series = fetch(country, ind.wb_code,
                               start_year=start_year, end_year=end_year)
                if not series:
                    continue

                rows = []
                for entry in series:
                    rows.append({
                        "country_code":   country,
                        "indicator_name": ind.indicator_name,
                        "period_end":     entry["period_end"],
                        # value & non-key columns:
                        "value":          entry["value"],
                        "unit":           ind.unit,
                        "dalio_power":    ind.dalio_power,
                        "period_start":   entry["period_start"],
                        "event_date":     entry["event_date"],
                        "source":         f"world_bank:{ind.wb_code}",
                        "backfill":       backfill,
                        "notes":          None,
                    })

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
                    job="ingest_country_indicators_worldbank",
                    table=f"cr_country_indicators/{country}/{ind.indicator_name}",
                )
                grand_total.inserted += result.inserted
                grand_total.revised  += result.revised
                grand_total.skipped  += result.skipped
                grand_total.errors.extend(result.errors)

    grand_total.log_summary(job="ingest_country_indicators_worldbank",
                            table="cr_country_indicators")


if __name__ == "__main__":
    backfill_from_year = None
    if len(sys.argv) > 2 and sys.argv[1] == "--backfill-from-year":
        backfill_from_year = int(sys.argv[2])
    run(backfill_from_year=backfill_from_year)
