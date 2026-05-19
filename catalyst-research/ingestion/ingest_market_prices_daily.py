"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/ingestion/ingest_market_prices_daily.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Layer 2 daily ingestion for non-security market series:
                      indices (HSI, S&P 500, ASX 200, Shanghai Composite),
                      FX (USD/HKD, USD/CNY, AUD/USD, USD/Gold), and government
                      bond yields (US 10Y). Primary source: Yahoo Finance via
                      yfinance. Fallback: Stooq CSV (added only if yfinance
                      proves unreliable in production — keep simple for v1).

Cadence             : Daily, post-close. Cron: 30 22 * * 1-5 UTC.
Writes to           : cr_market_prices

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §2.1
                      v1 series list per architecture §8 ("Indices and FX — Eight")
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


# -----------------------------------------------------------------------------
# Series registry — v1 scope
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class SeriesSpec:
    series_id: str          # canonical id stored in cr_market_prices.series_id
    series_type: str        # index | fx | yield | commodity
    yahoo_symbol: str       # yfinance ticker

SERIES: list[SeriesSpec] = [
    # Indices
    SeriesSpec("index.HSI",                  "index", "^HSI"),
    SeriesSpec("index.SP500",                "index", "^GSPC"),
    SeriesSpec("index.ASX200",               "index", "^AXJO"),
    SeriesSpec("index.SHANGHAI_COMPOSITE",   "index", "000001.SS"),
    # FX
    SeriesSpec("fx.USDHKD",                  "fx",    "USDHKD=X"),
    SeriesSpec("fx.USDCNY",                  "fx",    "USDCNY=X"),
    SeriesSpec("fx.AUDUSD",                  "fx",    "AUDUSD=X"),
    # Note: USD/Gold appears in the architecture series list. Yahoo's GC=F is
    # gold futures continuous; XAUUSD=X is the spot proxy. Spot is the right
    # signal for the COFER-gold thesis (Plan 2).
    SeriesSpec("fx.USDXAU",                  "fx",    "XAUUSD=X"),
    # Yields
    SeriesSpec("yield.US10Y",                "yield", "^TNX"),
]


# -----------------------------------------------------------------------------
# Fetch
# -----------------------------------------------------------------------------

def fetch_one(spec: SeriesSpec, *, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Fetch OHLCV bars for one series. Returns a DataFrame indexed by date
    with columns: open, high, low, close, volume. Empty DataFrame if the
    fetch fails or returns no rows.
    """
    try:
        df = yf.download(
            spec.yahoo_symbol,
            start=start.isoformat(),
            end=(end + dt.timedelta(days=1)).isoformat(),  # yfinance end is exclusive
            progress=False,
            auto_adjust=False,
        )
    except Exception as e:  # noqa: BLE001
        log.error("market_prices.fetch_failed", series=spec.series_id, error=str(e))
        return pd.DataFrame()

    if df.empty:
        log.warning("market_prices.empty", series=spec.series_id, symbol=spec.yahoo_symbol)
        return df

    # yfinance returns MultiIndex columns when multiple tickers; flatten just in case.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.rename(columns=str.lower)
    return df


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def run(*, lookback_days: int = 5, backfill_from: dt.date | None = None) -> None:
    """Ingest the daily window for all SERIES.

    Default behaviour: walk the last `lookback_days` trading days for every
    series, INSERT new rows, skip already-present-and-equal rows, INSERT
    revisions where the value differs. The look-back covers weekends and
    occasional missed days; idempotency handles re-runs cheaply.

    backfill_from : if set, run with backfill=true and a much wider window.
                    Used once during initial population.
    """
    end = dt.date.today()
    if backfill_from is not None:
        start = backfill_from
        backfill = True
    else:
        start = end - dt.timedelta(days=lookback_days)
        backfill = False

    log.info("market_prices.run.start",
             start=start.isoformat(), end=end.isoformat(),
             backfill=backfill, series_count=len(SERIES))

    grand_total = _adapter.UpsertResult()

    with _adapter.connect() as conn:
        for spec in SERIES:
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
                    "series_type": spec.series_type,
                    "open":   _nan_to_none(bar.get("open")),
                    "high":   _nan_to_none(bar.get("high")),
                    "low":    _nan_to_none(bar.get("low")),
                    "close":  float(close),
                    "volume": _nan_to_none(bar.get("volume"),
                                           cast=lambda v: int(v) if v else None),
                    "source": "yahoo_finance",
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
            result.log_summary(job="ingest_market_prices_daily",
                               table=f"cr_market_prices/{spec.series_id}")
            grand_total.inserted += result.inserted
            grand_total.revised  += result.revised
            grand_total.skipped  += result.skipped
            grand_total.errors.extend(result.errors)

    grand_total.log_summary(job="ingest_market_prices_daily", table="cr_market_prices")


def _nan_to_none(v, *, cast=float):
    if v is None or pd.isna(v):
        return None
    return cast(v)


if __name__ == "__main__":
    # Optional CLI: --backfill-from YYYY-MM-DD
    backfill_from = None
    if len(sys.argv) > 2 and sys.argv[1] == "--backfill-from":
        backfill_from = dt.date.fromisoformat(sys.argv[2])
    run(backfill_from=backfill_from)
