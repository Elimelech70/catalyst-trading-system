"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/ingestion/ingest_security_prices_daily.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Layer 2/3 daily ingestion of HKEX security price bars
                      via Moomoo OpenD. Reads the v1 watchlist from the
                      shared securities table (where listing_country='HKG')
                      and fetches one daily bar per security per trading day.

                      The Moomoo OpenD daemon runs on the intl droplet at
                      127.0.0.1:11111. This job MUST run on the intl droplet.

Cadence             : Daily, post-HKEX-close. Cron: 30 8 * * 1-5 UTC
                      (HKEX closes 16:00 HKT = 08:00 UTC).
Writes to           : cr_security_prices

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §2.1
                      Architecture §6.3 — one Moomoo ingestion, two readers
                      (intl trading + research).

IMPORTANT: This file uses the moomoo-api package the same way catalyst-
international does. If the intl side uses a forked client (e.g.
brokers/moomoo_client.py), reuse that client by `from ... import` rather
than re-implementing. The simplest v1 implementation below uses the
public moomoo-api directly; replace with the intl client once verified.
"""

from __future__ import annotations

import datetime as dt
import os
import sys

import structlog

from ingestion import _adapter

log = structlog.get_logger()


def _moomoo_quote_context():
    """Lazy import + connect. Kept local so the rest of the module imports
    cleanly even on machines without moomoo-api installed (e.g. CI).
    """
    from moomoo import OpenQuoteContext  # type: ignore

    host = os.environ.get("MOOMOO_HOST", "127.0.0.1")
    port = int(os.environ.get("MOOMOO_PORT", "11111"))
    return OpenQuoteContext(host=host, port=port)


def _list_hkg_securities(conn) -> list[tuple[int, str]]:
    """Return [(security_id, symbol)] for every HKG-listed security in the
    shared `securities` table. The watchlist IS the table — no separate file.
    """
    sql = (
        "SELECT s.security_id, s.symbol "
        "FROM securities s "
        "WHERE s.listing_country = 'HKG' "
        "ORDER BY s.symbol"
    )
    with conn.cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def _normalize_hkex_symbol(symbol: str) -> str:
    """Moomoo expects symbols like 'HK.00700' (5-digit, zero-padded). The
    intl securities table may store them as '0700', '00700', or '700'.
    Normalize defensively.
    """
    digits = "".join(c for c in symbol if c.isdigit())
    if not digits:
        raise ValueError(f"unparseable HKEX symbol: {symbol!r}")
    return f"HK.{digits.zfill(5)}"


def fetch_one(quote_ctx, *, moomoo_symbol: str,
              start: dt.date, end: dt.date) -> list[dict]:
    """Fetch daily K-line bars for one security. Returns a list of bar dicts.
    Empty list if the call fails or returns nothing.
    """
    from moomoo import KLType, AuType  # type: ignore

    ret, df, _page_key = quote_ctx.request_history_kline(
        code=moomoo_symbol,
        start=start.isoformat(),
        end=end.isoformat(),
        ktype=KLType.K_DAY,
        autype=AuType.QFQ,
        fields=["code", "time_key", "open", "close", "high", "low",
                "volume", "turnover"],
    )
    if ret != 0:
        log.error("security_prices.fetch_failed",
                  symbol=moomoo_symbol, error=str(df))
        return []
    if df is None or df.empty:
        return []

    rows = []
    for _, bar in df.iterrows():
        try:
            trade_date = dt.datetime.fromisoformat(str(bar["time_key"])[:10]).date()
        except Exception:  # noqa: BLE001
            continue
        rows.append({
            "trade_date": trade_date,
            "open":       float(bar["open"])   if bar.get("open")   is not None else None,
            "high":       float(bar["high"])   if bar.get("high")   is not None else None,
            "low":        float(bar["low"])    if bar.get("low")    is not None else None,
            "close":      float(bar["close"]),
            "volume":     int(bar["volume"])   if bar.get("volume") is not None else None,
            "adj_close":  None,  # Moomoo QFQ already adjusted; leaves room for raw later
        })
    return rows


def run(*, lookback_days: int = 5, backfill_from: dt.date | None = None) -> None:
    end = dt.date.today()
    if backfill_from is not None:
        start = backfill_from
        backfill = True
    else:
        start = end - dt.timedelta(days=lookback_days)
        backfill = False

    log.info("security_prices.run.start",
             start=start.isoformat(), end=end.isoformat(), backfill=backfill)

    grand_total = _adapter.UpsertResult()

    with _adapter.connect() as conn:
        securities = _list_hkg_securities(conn)
        log.info("security_prices.watchlist", count=len(securities))

        if not securities:
            log.warning("security_prices.watchlist_empty",
                        msg="No HKG-listed securities in shared table. "
                            "Run 003_seed_securities.sql or update intl-side "
                            "rows with listing_country='HKG'.")
            return

        quote_ctx = _moomoo_quote_context()
        try:
            for security_id, symbol in securities:
                try:
                    moomoo_symbol = _normalize_hkex_symbol(symbol)
                except ValueError as e:
                    log.warning("security_prices.skip_unparseable_symbol",
                                symbol=symbol, error=str(e))
                    continue

                bars = fetch_one(quote_ctx,
                                 moomoo_symbol=moomoo_symbol,
                                 start=start, end=end)
                if not bars:
                    continue

                rows = []
                for b in bars:
                    rows.append({
                        "security_id": security_id,
                        "trade_date":  b["trade_date"],
                        "open":   b["open"],
                        "high":   b["high"],
                        "low":    b["low"],
                        "close":  b["close"],
                        "volume": b["volume"],
                        "adj_close": b["adj_close"],
                        "source": "moomoo_opend",
                        "backfill": backfill,
                    })

                result = _adapter.upsert_facts(
                    conn,
                    table="cr_security_prices",
                    rows=rows,
                    business_key_columns=("security_id", "trade_date"),
                    value_columns=("close", "open", "high", "low", "volume", "adj_close"),
                    value_compare_column="close",
                )
                result.log_summary(
                    job="ingest_security_prices_daily",
                    table=f"cr_security_prices/{moomoo_symbol}",
                )
                grand_total.inserted += result.inserted
                grand_total.revised  += result.revised
                grand_total.skipped  += result.skipped
                grand_total.errors.extend(result.errors)
        finally:
            try:
                quote_ctx.close()
            except Exception:  # noqa: BLE001
                pass

    grand_total.log_summary(job="ingest_security_prices_daily",
                            table="cr_security_prices")


if __name__ == "__main__":
    backfill_from = None
    if len(sys.argv) > 2 and sys.argv[1] == "--backfill-from":
        backfill_from = dt.date.fromisoformat(sys.argv[2])
    run(backfill_from=backfill_from)
