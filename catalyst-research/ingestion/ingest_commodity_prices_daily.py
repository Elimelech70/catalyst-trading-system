"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/ingestion/ingest_commodity_prices_daily.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Layer 2 daily ingestion for the four v1 commodities:
                        - iron ore (CFR Qingdao 62% Fe) — primary signal
                          for the China-demand thesis (Plan 1)
                        - copper (LME spot; COMEX cross-ref)
                        - gold (London PM fix) — signal for Plan 2
                        - Brent crude (ICE settlement)

                      Yahoo Finance provides usable proxies for copper, gold,
                      and Brent (continuous futures). Iron ore CFR Qingdao
                      is NOT cleanly on yfinance; v1 uses TIO=F (SGX iron ore
                      62% futures) as the closest free proxy and flags it
                      with source='sgx_iron_ore_futures_proxy' so the
                      provenance is honest.

Cadence             : Daily, post-close. Cron: 45 22 * * 1-5 UTC.
Writes to           : cr_market_prices (series_type='commodity')

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §2.1
                      Architecture §8 ("Commodities — Four")
"""

from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass

import pandas as pd
import structlog
import yfinance as yf

from ingestion import _adapter

log = structlog.get_logger()


@dataclass(frozen=True)
class CommoditySpec:
    series_id: str
    yahoo_symbol: str
    source_label: str

# Note: v1 deliberately uses simple yfinance proxies. Higher-fidelity sources
# (LME official, London PM fix from LBMA, CFR Qingdao from Platts/Argus) are
# paywalled or require scraping. The proxies are good enough to validate the
# learning plans; upgrade in v1.5 if a plan demands it.
COMMODITIES: list[CommoditySpec] = [
    CommoditySpec(
        series_id="commodity.iron_ore",
        yahoo_symbol="TIO=F",   # SGX iron ore 62% Fe futures (proxy for CFR Qingdao)
        source_label="sgx_iron_ore_futures_proxy",
    ),
    CommoditySpec(
        series_id="commodity.copper",
        yahoo_symbol="HG=F",    # COMEX copper continuous
        source_label="comex_copper_futures",
    ),
    CommoditySpec(
        series_id="commodity.gold",
        yahoo_symbol="GC=F",    # COMEX gold continuous (proxy for London PM fix)
        source_label="comex_gold_futures_proxy",
    ),
    CommoditySpec(
        series_id="commodity.brent",
        yahoo_symbol="BZ=F",    # ICE Brent continuous
        source_label="ice_brent_futures",
    ),
]


def fetch_one(spec: CommoditySpec, *, start: dt.date, end: dt.date) -> pd.DataFrame:
    try:
        df = yf.download(
            spec.yahoo_symbol,
            start=start.isoformat(),
            end=(end + dt.timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=False,
        )
    except Exception as e:  # noqa: BLE001
        log.error("commodity.fetch_failed", series=spec.series_id, error=str(e))
        return pd.DataFrame()

    if df.empty:
        log.warning("commodity.empty", series=spec.series_id, symbol=spec.yahoo_symbol)
        return df

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.rename(columns=str.lower)
    return df


def run(*, lookback_days: int = 5, backfill_from: dt.date | None = None) -> None:
    end = dt.date.today()
    if backfill_from is not None:
        start = backfill_from
        backfill = True
    else:
        start = end - dt.timedelta(days=lookback_days)
        backfill = False

    log.info("commodity.run.start",
             start=start.isoformat(), end=end.isoformat(),
             backfill=backfill, count=len(COMMODITIES))

    grand_total = _adapter.UpsertResult()

    with _adapter.connect() as conn:
        for spec in COMMODITIES:
            df = fetch_one(spec, start=start, end=end)
            if df.empty:
                continue

            rows = []
            for ts, bar in df.iterrows():
                trade_date = ts.date() if hasattr(ts, "date") else ts
                close = bar.get("close")
                if close is None or pd.isna(close):
                    continue
                rows.append({
                    "series_id":   spec.series_id,
                    "trade_date":  trade_date,
                    "series_type": "commodity",
                    "open":   _nan_to_none(bar.get("open")),
                    "high":   _nan_to_none(bar.get("high")),
                    "low":    _nan_to_none(bar.get("low")),
                    "close":  float(close),
                    "volume": _nan_to_none(bar.get("volume"),
                                           cast=lambda v: int(v) if v else None),
                    "source": spec.source_label,
                    "backfill": backfill,
                })

            result = _adapter.upsert_facts(
                conn,
                table="cr_market_prices",
                rows=rows,
                business_key_columns=("series_id", "trade_date"),
                value_columns=("close", "open", "high", "low", "volume", "series_type"),
                value_compare_column="close",
            )
            result.log_summary(job="ingest_commodity_prices_daily",
                               table=f"cr_market_prices/{spec.series_id}")
            grand_total.inserted += result.inserted
            grand_total.revised  += result.revised
            grand_total.skipped  += result.skipped
            grand_total.errors.extend(result.errors)

    grand_total.log_summary(job="ingest_commodity_prices_daily", table="cr_market_prices")


def _nan_to_none(v, *, cast=float):
    if v is None or pd.isna(v):
        return None
    return cast(v)


if __name__ == "__main__":
    backfill_from = None
    if len(sys.argv) > 2 and sys.argv[1] == "--backfill-from":
        backfill_from = dt.date.fromisoformat(sys.argv[2])
    run(backfill_from=backfill_from)
