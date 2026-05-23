"""
Name of Application : Catalyst Trading System
Name of file        : catalyst-research/ingestion/ingest_hkex_disclosure_feed.py
Version             : 0.1.0
Last Updated        : 2026-05-18
Purpose             : Layer 3 news ingestion from the HKEX disclosure feed.
                      Polls the feed every 15 minutes during HKEX trading
                      hours, dedupes on (source, external_id), and links each
                      event to the corresponding security in the shared
                      `securities` table by HKEX stock code.

Cadence             : Every 15 minutes during HKEX hours. Cron:
                      */15 1-9 * * 1-5 UTC (HKT 09:00-17:00).
Writes to           : cr_news_events, cr_news_securities

Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §2.1
                      Architecture §3 ("Layer 3: News and Securities-Level Data")

STATUS              : The feed URL and JSON shape are sketched here from
                      public documentation. The exact field names vary by
                      HKEX endpoint version; the parser is defensive but the
                      first live run on the intl droplet will need spot
                      verification against actual payloads.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import requests
import structlog

from ingestion import _adapter

log = structlog.get_logger()

DEFAULT_HKEX_URL = (
    "https://www1.hkexnews.hk/ncms/script/eds/eds_newsfile_en.json"
)
HKEX_STOCK_CODE_RE = re.compile(r"\b(\d{4,5})\.HK\b|\(stock code:?\s*(\d{4,5})\)", re.I)


def _feed_url() -> str:
    return os.environ.get("HKEX_FEED_URL", DEFAULT_HKEX_URL)


def fetch_feed() -> list[dict]:
    """Fetch the current disclosure-feed payload. Returns a list of raw
    item dicts, or empty list on failure.
    """
    url = _feed_url()
    try:
        resp = requests.get(url, timeout=30,
                            headers={"User-Agent": "catalyst-research/0.1"})
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:  # noqa: BLE001
        log.error("hkex_disclosure.fetch_failed", url=url, error=str(e))
        return []

    # The feed wraps items in different keys across endpoint versions; try
    # the common shapes.
    for key in ("items", "results", "data", "newsList"):
        if isinstance(payload, dict) and isinstance(payload.get(key), list):
            return payload[key]
    if isinstance(payload, list):
        return payload
    log.warning("hkex_disclosure.unknown_shape",
                top_keys=list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)
    return []


def _extract_event_date(item: dict) -> datetime:
    for key in ("releaseTime", "newsTime", "publishedTime", "dateTime", "date"):
        v = item.get(key)
        if not v:
            continue
        try:
            # Accept either ISO-8601 or "YYYY-MM-DD HH:MM:SS"
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.strptime(str(v), "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
    return datetime.now(timezone.utc)


def _extract_external_id(item: dict) -> str | None:
    for key in ("newsId", "id", "messageId", "externalId"):
        v = item.get(key)
        if v:
            return str(v)
    return None


def _extract_headline(item: dict) -> str:
    for key in ("headline", "title", "subject", "summary"):
        v = item.get(key)
        if v:
            return str(v).strip()
    return ""


def _extract_body(item: dict) -> str | None:
    for key in ("body", "content", "description"):
        v = item.get(key)
        if v:
            return str(v)
    return None


def _extract_hkex_codes(item: dict) -> list[str]:
    """Find HKEX stock codes referenced in the item. Looks at explicit
    fields first, then falls back to scanning headline/body text.
    """
    codes: set[str] = set()
    for key in ("stockCodes", "stockCode", "securities", "tickers"):
        v = item.get(key)
        if isinstance(v, list):
            for c in v:
                d = re.sub(r"\D", "", str(c))
                if d:
                    codes.add(d.zfill(5))
        elif v:
            d = re.sub(r"\D", "", str(v))
            if d:
                codes.add(d.zfill(5))
    haystack = " ".join(
        str(item.get(k, "")) for k in ("headline", "title", "summary", "body")
    )
    for m in HKEX_STOCK_CODE_RE.finditer(haystack):
        digits = next(g for g in m.groups() if g)
        codes.add(digits.zfill(5))
    return sorted(codes)


def _security_id_for_hkex_code(conn, code5: str) -> int | None:
    """The intl `securities` table stores HKEX symbols in its own
    convention. Try a few likely formats and return the first match.
    """
    candidates = [code5, code5.lstrip("0"), f"HK.{code5}", f"{code5}.HK"]
    for s in candidates:
        sid = _adapter.security_id_for_symbol(conn, symbol=s, exchange_code="HKEX")
        if sid is not None:
            return sid
    return None


def run() -> None:
    items = fetch_feed()
    log.info("hkex_disclosure.run.start", item_count=len(items))
    if not items:
        return

    inserted = 0
    deduped = 0
    linked = 0

    with _adapter.connect() as conn:
        for item in items:
            external_id = _extract_external_id(item)
            headline = _extract_headline(item)
            if not headline:
                continue

            new_id = _adapter.insert_news_event(
                conn,
                source="HKEX_disclosure",
                external_id=external_id,
                headline=headline,
                body=_extract_body(item),
                event_date=_extract_event_date(item),
                classification=None,   # v1: no classifier
                raw_payload=item,
            )
            if new_id is None:
                deduped += 1
                continue
            inserted += 1

            for code in _extract_hkex_codes(item):
                sid = _security_id_for_hkex_code(conn, code)
                if sid is not None:
                    _adapter.link_news_security(conn,
                                                news_event_id=new_id,
                                                security_id=sid)
                    linked += 1

    log.info("hkex_disclosure.run.done",
             inserted=inserted, deduped=deduped, linked=linked)


if __name__ == "__main__":
    run()
