"""
Catalyst Neural — News Collector

Captures news headlines with source provenance and precise timestamps.
The network will learn which sources from which tiers at which timing
correlate with which outcomes. We don't pre-judge — we record.

Source tier assignment uses Craig's news-sources-guide.md as foundation.
"""

import sys
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.database import store_news, get_active_securities
from config.settings import NEWSAPI_KEY, FINNHUB_KEY, get_source_tier


def collect_newsapi(query=None, symbols=None, days_back=1):
    """
    Collect news from NewsAPI.org.
    Free tier: 100 requests/day, articles up to 1 month old.
    """
    if not NEWSAPI_KEY:
        print("NewsAPI key not set. Set NEWSAPI_KEY environment variable.")
        return 0
    
    url = "https://newsapi.org/v2/everything"
    
    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    params = {
        "apiKey": NEWSAPI_KEY,
        "from": from_date,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 100,
    }
    
    if query:
        params["q"] = query
    elif symbols:
        params["q"] = " OR ".join(symbols)
    else:
        # Default: broad financial news
        params["q"] = "stock market OR economy OR federal reserve OR trade war OR BRICS"
        params["domains"] = "reuters.com,bloomberg.com,ft.com,wsj.com,bbc.co.uk,cnbc.com"
    
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        articles = data.get("articles", [])
        stored = 0
        
        for article in articles:
            source_name = article.get("source", {}).get("name", "unknown")
            headline = article.get("title", "")
            
            if not headline or headline == "[Removed]":
                continue
            
            published_at = article.get("publishedAt", "")
            author = article.get("author")
            article_url = article.get("url")
            description = article.get("description", "")
            content = article.get("content", "")
            snippet = (description or content or "")[:500]
            
            # Determine which symbols this relates to
            related_symbols = None
            if symbols:
                # Check if any watched symbol appears in headline or description
                text = f"{headline} {description}".upper()
                related = [s for s in symbols if s.upper() in text]
                if related:
                    related_symbols = ",".join(related)
            
            store_news(
                headline=headline,
                source=source_name,
                source_tier=get_source_tier(source_name),
                published_at=published_at,
                symbols=related_symbols,
                author=author,
                url=article_url,
                content_snippet=snippet
            )
            stored += 1
        
        print(f"  NewsAPI: {stored} articles stored")
        return stored
        
    except Exception as e:
        print(f"  NewsAPI ERROR: {e}")
        return 0


def collect_finnhub_news(symbol=None, market="US"):
    """
    Collect news from Finnhub.
    Free tier: 60 calls/minute.
    Returns company-specific news with better symbol mapping.
    """
    if not FINNHUB_KEY:
        print("Finnhub key not set. Set FINNHUB_KEY environment variable.")
        return 0
    
    url = "https://finnhub.io/api/v1"
    
    if symbol:
        # Company news
        endpoint = f"{url}/company-news"
        from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = datetime.utcnow().strftime("%Y-%m-%d")
        params = {
            "symbol": symbol,
            "from": from_date,
            "to": to_date,
            "token": FINNHUB_KEY
        }
    else:
        # General market news
        endpoint = f"{url}/news"
        params = {
            "category": "general",
            "token": FINNHUB_KEY
        }
    
    try:
        resp = requests.get(endpoint, params=params, timeout=30)
        resp.raise_for_status()
        articles = resp.json()
        
        if not isinstance(articles, list):
            return 0
        
        stored = 0
        for article in articles:
            headline = article.get("headline", "")
            source_name = article.get("source", "unknown")
            
            if not headline:
                continue
            
            # Finnhub gives Unix timestamp
            ts = article.get("datetime", 0)
            published_at = datetime.utcfromtimestamp(ts).isoformat() if ts else ""
            
            store_news(
                headline=headline,
                source=source_name,
                source_tier=get_source_tier(source_name),
                published_at=published_at,
                symbols=symbol,
                markets=market,
                url=article.get("url"),
                content_snippet=article.get("summary", "")[:500]
            )
            stored += 1
        
        print(f"  Finnhub ({symbol or 'general'}): {stored} articles stored")
        return stored
        
    except Exception as e:
        print(f"  Finnhub ERROR: {e}")
        return 0


def collect_all_news():
    """
    Collect news for all active securities + general market news.
    """
    print(f"\n{'='*60}")
    print(f"News Collection Run — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")
    
    total = 0
    
    # General financial news via NewsAPI
    securities = get_active_securities()
    us_symbols = [s["symbol"] for s in securities if s["market"] == "US"]
    
    if us_symbols:
        total += collect_newsapi(symbols=us_symbols[:5])  # API limit friendly
        time.sleep(1)
    
    # Broad macro/geopolitical news
    total += collect_newsapi(query="economy OR interest rates OR trade OR sanctions OR BRICS OR oil")
    time.sleep(1)
    
    # Per-security news via Finnhub (US only — Finnhub is US-focused)
    for sym in us_symbols[:10]:  # limit to avoid rate limiting
        total += collect_finnhub_news(symbol=sym, market="US")
        time.sleep(1.5)  # respect rate limit
    
    # General market news via Finnhub
    total += collect_finnhub_news()
    
    print(f"\nTotal news articles collected: {total}")
    return total


if __name__ == "__main__":
    collect_all_news()
