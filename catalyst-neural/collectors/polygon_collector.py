"""
Catalyst Neural — Polygon.io Collector

Replaces yfinance + NewsAPI + Finnhub for US market data. Sized for the
cohort experiments universe (~300 US symbols × 5 years of 5m candles +
historical news with per-ticker metadata).

Polygon Starter tier ($29/mo):
  - All historical REST endpoints (aggregates, news, reference)
  - 5 years intraday history
  - News API with per-article ticker tagging + publisher metadata
  - Delayed real-time data (~15 min lag, no WebSocket)
  - Defensive rate target: ~4 req/sec (no documented hard limit on paid plans)

Endpoints used:
  /v2/aggs/ticker/{ticker}/range/{m}/{tspan}/{from}/{to}   — OHLCV bars
  /v2/reference/news                                       — news with metadata
  /v3/reference/tickers                                    — universe discovery

Idempotency: candle and news stores use INSERT OR IGNORE on natural keys, so
re-running this is safe.
"""

import sys
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.database import store_candles, store_news, get_active_securities, add_security
from config.settings import POLYGON_API_KEY

POLYGON_BASE = "https://api.polygon.io"
REQ_PAUSE_SEC = 0.25   # ~4 req/sec — well under Polygon's paid-tier capacity
DEFAULT_LOOKBACK_DAYS = 5 * 365
CANDLE_BATCH_SIZE = 5_000
NEWS_PAGE_SIZE = 1_000

# Polygon publishers mapped to Catalyst's news-source taxonomy.
# Anything NOT in this map is treated as tier 99 (unknown) and skipped by default.
# Maintenance note: when you see useful publishers in the
# "unknown publishers" report at end of backfill, add them here.
_PUBLISHER_TIER = {
    # Tier 1 — wire services (ground truth, fastest)
    "Reuters": 1, "Reuters News": 1,
    "Bloomberg": 1, "Bloomberg News": 1, "Bloomberg.com": 1, "Bloomberg Markets": 1,
    "Dow Jones": 1, "Dow Jones Newswires": 1, "Dow Jones & Co.": 1,
    "AP": 1, "Associated Press": 1, "AP News": 1,
    "AFP": 1, "Agence France-Presse": 1,
    # Tier 1 — primary corporate press-release wires
    # These distribute companies' own announcements (earnings releases,
    # FDA approvals, M&A, IPO terms) — closer to the source than any
    # secondary outlet. The cohort experiment cares specifically about
    # catalyst-event news; these wires are where catalyst events appear
    # first. (Polygon dominantly carries GlobeNewswire content.)
    "GlobeNewswire Inc.": 1, "GlobeNewswire": 1, "Globe Newswire": 1,
    "Business Wire": 1, "BusinessWire": 1, "businesswire.com": 1,
    "PR Newswire": 1, "PRNewswire": 1, "prnewswire.com": 1,
    "PR Web": 1, "PRWeb": 1,
    "Accesswire": 1, "ACCESSWIRE": 1, "accesswire.com": 1,
    "EDGAR": 1, "SEC": 1, "U.S. Securities and Exchange Commission": 1,
    # Tier 2 — major outlets (reliable, slight delay)
    "WSJ": 2, "Wall Street Journal": 2, "Wall Street Journal Online": 2,
    "Financial Times": 2, "Financial Times Limited": 2, "FT.com": 2,
    "CNBC": 2, "CNBC.com": 2,
    "Barron's": 2, "Barron's Online": 2,
    "Forbes": 2, "Forbes Digital": 2, "Forbes.com": 2,
    "MarketWatch": 2, "MarketWatch.com": 2,
    "Investor's Business Daily": 2, "IBD": 2,
    "The Economist": 2,
    "Investing.com": 2, "Investing": 2,
    # Tier 3 — secondary / aggregators (useful but noisy — currently EXCLUDED)
    "Seeking Alpha": 3, "The Motley Fool": 3, "Motley Fool": 3,
    "Zacks": 3, "Zacks Investment Research": 3,
    "Benzinga": 3, "Yahoo Finance": 3, "InvestorPlace": 3,
    "TipRanks": 3, "GuruFocus": 3, "TheStreet": 3,
    # Tier 4 — social / alternative (high noise — currently EXCLUDED)
    "Reddit": 4, "StockTwits": 4, "Twitter": 4,
}

# Default tier for unknown publishers — flagged for review, excluded from ingestion
# when MAX_INGEST_TIER < 99. Tracked separately so we can extend the whitelist.
UNKNOWN_PUBLISHER_TIER = 99
MAX_INGEST_TIER_DEFAULT = 2   # keep Tier 1 + Tier 2 only


# ── HTTP helper ──────────────────────────────────────────────────────────

def _get(url, params=None, max_retries=4):
    """GET with bearer auth + exponential backoff on 429/5xx."""
    if not POLYGON_API_KEY:
        raise RuntimeError("POLYGON_API_KEY is not set in .env")
    headers = {"Authorization": f"Bearer {POLYGON_API_KEY}"}
    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params or {}, headers=headers, timeout=30)
            if r.status_code == 429:
                wait = 2 ** attempt
                print(f"    rate-limited, waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                print(f"    HTTP error after {max_retries} attempts: {e}")
                return None
            time.sleep(2 ** attempt)
    return None


# ── Candle aggregates ────────────────────────────────────────────────────

_TIMEFRAME_MAP = {
    "1m":  (1,  "minute"),
    "5m":  (5,  "minute"),
    "15m": (15, "minute"),
    "1h":  (1,  "hour"),
    "1d":  (1,  "day"),
}


def collect_polygon_candles(symbol, timeframe="5m", days_back=DEFAULT_LOOKBACK_DAYS):
    """
    Backfill OHLCV candles for one US symbol over the window [today-days_back, today].
    Uses unadjusted prices (we want raw OHLCV for training; adjustments are a
    separate label-engineering concern).

    Returns: count of bars stored (= newly inserted; duplicates skipped silently).
    """
    if timeframe not in _TIMEFRAME_MAP:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    multiplier, timespan = _TIMEFRAME_MAP[timeframe]

    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days_back)
    url = (f"{POLYGON_BASE}/v2/aggs/ticker/{symbol}/range/"
           f"{multiplier}/{timespan}/"
           f"{start_dt.strftime('%Y-%m-%d')}/{end_dt.strftime('%Y-%m-%d')}")
    params = {"adjusted": "false", "sort": "asc", "limit": 50_000}

    stored = 0
    batch = []
    next_url = url
    first_call = True
    while next_url:
        data = _get(next_url, params=(params if first_call else None))
        first_call = False
        if not data or data.get("status") not in ("OK", "DELAYED"):
            if data:
                print(f"    {symbol}: API status={data.get('status')} "
                      f"msg={data.get('message','')}")
            break

        for bar in data.get("results", []) or []:
            # Polygon bar fields: t (ms epoch), o, h, l, c, v, vw (vwap), n (trade count)
            ts = datetime.utcfromtimestamp(bar["t"] / 1000).isoformat()
            batch.append({
                "symbol":      symbol,
                "market":      "US",
                "timeframe":   timeframe,
                "timestamp":   ts,
                "open":        bar["o"],
                "high":        bar["h"],
                "low":         bar["l"],
                "close":       bar["c"],
                "volume":      bar["v"],
                "vwap":        bar.get("vw"),
                "trade_count": bar.get("n"),
            })
            if len(batch) >= CANDLE_BATCH_SIZE:
                store_candles(batch)
                stored += len(batch)
                batch = []

        next_url = data.get("next_url")
        if next_url:
            time.sleep(REQ_PAUSE_SEC)

    if batch:
        store_candles(batch)
        stored += len(batch)

    return stored


# ── News ─────────────────────────────────────────────────────────────────

def collect_polygon_news(symbol=None, days_back=DEFAULT_LOOKBACK_DAYS,
                        max_pages=200, max_tier=MAX_INGEST_TIER_DEFAULT,
                        unknown_tracker=None):
    """
    Backfill news. If symbol is given, filters to that ticker; otherwise
    pulls market-wide news.

    Polygon's news payload includes:
      - title, description, article_url, published_utc, author
      - publisher.name, publisher.favicon_url
      - tickers: [list of related symbols]
      - keywords: [optional list]
      - insights: [per-ticker sentiment + reasoning]

    Source-tier filtering: articles whose publisher is NOT mapped in
    `_PUBLISHER_TIER` (or maps to a tier > max_tier) are SKIPPED. The default
    max_tier=2 keeps wire services + major outlets only, which is what the
    Phase 2 regex classifier was designed for. Unknown-publisher names are
    counted into `unknown_tracker` (a Counter passed by the orchestrator) so
    we can expand the whitelist iteratively.

    Returns: dict {stored, skipped_low_tier, skipped_unknown}
    """
    from collections import Counter
    start_dt = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    url = f"{POLYGON_BASE}/v2/reference/news"
    params = {
        "published_utc.gte": start_dt,
        "order": "asc",
        "sort": "published_utc",
        "limit": NEWS_PAGE_SIZE,
    }
    if symbol:
        params["ticker"] = symbol

    stored = 0
    skipped_low_tier = 0
    skipped_unknown = 0
    next_url = url
    first_call = True
    pages = 0
    while next_url and pages < max_pages:
        pages += 1
        data = _get(next_url, params=(params if first_call else None))
        first_call = False
        if not data:
            break

        for article in data.get("results", []) or []:
            publisher_name = (article.get("publisher") or {}).get("name", "unknown")
            # Source-tier gate — applied BEFORE store_news so low-tier rows
            # never reach the DB or the regex classifier.
            if publisher_name in _PUBLISHER_TIER:
                tier = _PUBLISHER_TIER[publisher_name]
                if tier > max_tier:
                    skipped_low_tier += 1
                    continue
            else:
                skipped_unknown += 1
                if unknown_tracker is not None:
                    unknown_tracker[publisher_name] += 1
                continue   # unknown -> skip by default

            tickers = article.get("tickers") or []
            symbols_field = ",".join(tickers) if tickers else None
            store_news(
                headline=article.get("title", "")[:500],
                source=publisher_name,
                source_tier=tier,
                published_at=article.get("published_utc"),
                symbols=symbols_field,
                markets="US",
                author=article.get("author"),
                url=article.get("article_url"),
                content_snippet=(article.get("description") or "")[:500],
                classify=True,
            )
            stored += 1

        next_url = data.get("next_url")
        if next_url:
            time.sleep(REQ_PAUSE_SEC)

    return {"stored": stored,
            "skipped_low_tier": skipped_low_tier,
            "skipped_unknown": skipped_unknown}


# ── Universe discovery ───────────────────────────────────────────────────

def discover_us_universe(limit=300, min_dollar_volume=10_000_000):
    """
    Discover the top US stocks by previous-day dollar volume.

    Method: pull Polygon's all-tickers snapshot in one call (~3 MB, 12K
    tickers), rank by previous-day `close × volume` (dollar volume),
    return the top `limit`. Then enrich each with sector/name from the
    per-ticker reference endpoint.

    Dollar volume is a robust liquidity proxy that correlates well with
    market cap and trading interest — the symbols our cohort experiment
    actually cares about. We avoid Polygon's `/v3/reference/tickers`
    sort=market_cap (unsupported) and per-ticker details enrichment
    (would be 3000+ extra API calls).

    Returns list of dicts: {symbol, name, primary_exchange, dollar_volume_prev}
    """
    # 1. Pull the full-market snapshot in one shot
    url = f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/tickers"
    data = _get(url)
    if not data:
        return []
    rows = data.get("tickers", []) or []

    # 2. Compute prev-day dollar volume for each, filter, sort
    ranked = []
    for row in rows:
        prev = row.get("prevDay") or {}
        close = prev.get("c") or 0
        volume = prev.get("v") or 0
        dv = close * volume
        if dv < min_dollar_volume:
            continue
        ranked.append({
            "symbol":             row["ticker"],
            "dollar_volume_prev": dv,
            "close_prev":         close,
            "volume_prev":        volume,
        })
    ranked.sort(key=lambda r: r["dollar_volume_prev"], reverse=True)
    top = ranked[:limit]

    # 3. Enrich top-N with name + exchange from the per-ticker reference endpoint
    out = []
    for i, r in enumerate(top):
        if i % 50 == 0:
            print(f"    enriching {i}/{len(top)}...")
        details = _get(f"{POLYGON_BASE}/v3/reference/tickers/{r['symbol']}")
        time.sleep(REQ_PAUSE_SEC)
        if not details or not details.get("results"):
            r["name"] = ""
            r["primary_exchange"] = ""
            r["type"] = "?"
        else:
            d = details["results"]
            r["name"] = d.get("name", "")
            r["primary_exchange"] = d.get("primary_exchange", "")
            r["type"] = d.get("type", "?")
        out.append(r)

    return out


# ── Backfill orchestrator ────────────────────────────────────────────────

def backfill_universe(symbols=None, timeframe="5m",
                     days_back=DEFAULT_LOOKBACK_DAYS,
                     do_candles=True, do_news=True,
                     register_universe=False, universe_size=300):
    """
    Backfill candles + news for a list of US symbols.

    If symbols is None and register_universe=True, discovers the top
    `universe_size` US common stocks by market cap and adds any missing
    ones to the securities table before backfilling.
    """
    if symbols is None and register_universe:
        print(f">>> Discovering top {universe_size} US common stocks by market cap")
        discovered = discover_us_universe(limit=universe_size)
        for d in discovered:
            add_security(symbol=d["symbol"], market="US", name=d["name"],
                        source="polygon_discovery",
                        reason=f"dollar_volume_prev={int(d['dollar_volume_prev']):,}")
        symbols = [d["symbol"] for d in discovered]
        print(f"    registered {len(symbols)} symbols")

    if symbols is None:
        secs = get_active_securities(market="US")
        symbols = [s["symbol"] for s in secs]

    print(f"\nBackfilling {len(symbols)} US symbols for {days_back} days")
    print(f"  candles={do_candles}  news={do_news}  timeframe={timeframe}\n")

    t0 = time.time()
    total_bars = total_news = 0

    if do_candles:
        print(">>> Phase 1: Candles")
        for i, sym in enumerate(symbols, 1):
            print(f"  [{i}/{len(symbols)}] {sym}", end=" ", flush=True)
            try:
                n = collect_polygon_candles(sym, timeframe, days_back)
                total_bars += n
                print(f"→ {n:,} bars")
            except Exception as e:
                print(f"→ ERROR: {e}")
            time.sleep(REQ_PAUSE_SEC)

    from collections import Counter
    unknown_tracker = Counter()
    total_skipped_low_tier = 0
    total_skipped_unknown = 0

    if do_news:
        print("\n>>> Phase 2: Per-symbol news (Tier 1+2 only)")
        for i, sym in enumerate(symbols, 1):
            print(f"  [{i}/{len(symbols)}] {sym}", end=" ", flush=True)
            try:
                r = collect_polygon_news(sym, days_back,
                                         unknown_tracker=unknown_tracker)
                total_news += r["stored"]
                total_skipped_low_tier += r["skipped_low_tier"]
                total_skipped_unknown += r["skipped_unknown"]
                print(f"→ kept {r['stored']}  "
                      f"skipped {r['skipped_low_tier']}(T3+) "
                      f"+ {r['skipped_unknown']}(unknown)")
            except Exception as e:
                print(f"→ ERROR: {e}")
            time.sleep(REQ_PAUSE_SEC)

    elapsed = time.time() - t0
    print(f"\nBackfill complete in {elapsed/60:.1f} min")
    print(f"  Candles stored:        {total_bars:,}")
    print(f"  News articles kept:    {total_news:,}")
    print(f"  News skipped (T3+):    {total_skipped_low_tier:,}")
    print(f"  News skipped (unknown):{total_skipped_unknown:,}")

    if unknown_tracker:
        print("\nTop unknown publishers (consider adding to _PUBLISHER_TIER):")
        for pub, n in unknown_tracker.most_common(20):
            print(f"  {n:>6}  {pub}")

    return total_bars, total_news


# ── CLI entry ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Polygon.io backfill driver")
    p.add_argument("--discover", action="store_true",
                  help="Discover top US common stocks by market cap and register them")
    p.add_argument("--universe-size", type=int, default=300,
                  help="If --discover, how many symbols to register (default 300)")
    p.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS,
                  help=f"Lookback window in days (default {DEFAULT_LOOKBACK_DAYS} = 5y)")
    p.add_argument("--timeframe", default="5m", choices=list(_TIMEFRAME_MAP.keys()),
                  help="Candle timeframe (default 5m)")
    p.add_argument("--candles-only", action="store_true",
                  help="Skip news backfill")
    p.add_argument("--news-only", action="store_true",
                  help="Skip candle backfill")
    p.add_argument("--symbols", nargs="*", default=None,
                  help="Override universe with explicit symbol list")
    args = p.parse_args()

    backfill_universe(
        symbols=args.symbols,
        timeframe=args.timeframe,
        days_back=args.days,
        do_candles=not args.news_only,
        do_news=not args.candles_only,
        register_universe=args.discover,
        universe_size=args.universe_size,
    )
