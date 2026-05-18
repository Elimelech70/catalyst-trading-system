"""
News Sentiment Analysis Tool
============================
Fetches news and analyzes sentiment for trading decisions.

Name of Application: Catalyst Trading System
Name of file: news.py
Version: 2.0.0
Last Updated: 2026-01-24
Purpose: News fetching and sentiment analysis with external context configuration

REVISION HISTORY:
v2.0.0 (2026-01-24) - Architecture refactor: context separated from tool
  - Keywords, catalyst types, sectors now loaded from config/news_context.yaml
  - Hot-reload capability for context updates without code changes
  - Added catalyst type classification with tiered multipliers
  - Added sector correlation detection
v1.0.0 (2025-12-xx) - Initial implementation with embedded keywords

ARCHITECTURE:
  This tool (news.py) contains LOGIC only.
  Context (keywords, mappings, thresholds) lives in config/news_context.yaml.
  
  Benefits:
  - Update keywords without code changes
  - Version control context separately from code
  - Agent could potentially update own context (future)
  - Easy A/B testing of different keyword sets
"""

import os
import re
import logging
import yaml
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

# Hong Kong timezone
HK_TZ = ZoneInfo("Asia/Hong_Kong")

# =============================================================================
# CONTEXT LOADER
# =============================================================================

class NewsContext:
    """
    Loads and manages news context from external YAML configuration.
    
    Supports hot-reload: call reload() to pick up config changes without restart.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize context loader.
        
        Args:
            config_path: Path to news_context.yaml. If None, searches standard locations.
        """
        self._config_path = config_path or self._find_config()
        self._config: dict = {}
        self._last_loaded: Optional[datetime] = None
        self._load()
    
    def _find_config(self) -> str:
        """Find config file in standard locations."""
        search_paths = [
            Path(__file__).parent.parent / "config" / "news_context.yaml",
            Path("/root/catalyst-international/config/news_context.yaml"),
            Path("./config/news_context.yaml"),
            Path("../config/news_context.yaml"),
        ]
        
        for path in search_paths:
            if path.exists():
                return str(path)
        
        raise FileNotFoundError(
            f"news_context.yaml not found. Searched: {[str(p) for p in search_paths]}"
        )
    
    def _load(self) -> None:
        """Load configuration from YAML file."""
        try:
            with open(self._config_path, "r") as f:
                self._config = yaml.safe_load(f)
            self._last_loaded = datetime.now()
            logger.info(f"Loaded news context v{self.version} from {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to load news context: {e}")
            raise
    
    def reload(self) -> None:
        """Reload configuration from file (hot-reload)."""
        self._load()
        logger.info(f"Reloaded news context v{self.version}")
    
    @property
    def version(self) -> str:
        return self._config.get("version", "unknown")
    
    @property
    def positive_keywords(self) -> set[str]:
        return set(self._config.get("positive_keywords", []))
    
    @property
    def negative_keywords(self) -> set[str]:
        return set(self._config.get("negative_keywords", []))
    
    @property
    def catalyst_types(self) -> dict:
        return self._config.get("catalyst_types", {})
    
    @property
    def sectors(self) -> dict:
        return self._config.get("sectors", {})
    
    @property
    def stock_names(self) -> dict:
        return self._config.get("stock_names", {})
    
    @property
    def thresholds(self) -> dict:
        return self._config.get("thresholds", {})
    
    @property
    def composite_weights(self) -> dict:
        return self._config.get("composite_weights", {})
    
    def get_stock_name(self, symbol: str) -> str:
        """Get company name for stock symbol."""
        return self.stock_names.get(symbol, symbol)


# Global context instance (lazy loaded)
_context: Optional[NewsContext] = None


def get_context() -> NewsContext:
    """Get or create context singleton."""
    global _context
    if _context is None:
        _context = NewsContext()
    return _context


def reload_context() -> None:
    """Reload context from config file."""
    global _context
    if _context is not None:
        _context.reload()
    else:
        _context = NewsContext()


# =============================================================================
# CATALYST CLASSIFIER
# =============================================================================

@dataclass
class CatalystInfo:
    """Information about a detected catalyst."""
    tier: int
    type_id: str
    type_name: str
    keywords_matched: list[str]
    multiplier: float
    typical_move: str


class CatalystClassifier:
    """Classifies news headlines into catalyst tiers using external context."""
    
    def __init__(self, context: Optional[NewsContext] = None):
        self._context = context or get_context()
        self._build_keyword_index()
    
    def _build_keyword_index(self) -> None:
        """Build keyword to catalyst type lookup."""
        self._keyword_to_type = {}
        
        for type_id, config in self._context.catalyst_types.items():
            for keyword in config.get("keywords", []):
                self._keyword_to_type[keyword.lower()] = type_id
    
    def classify(self, headline: str) -> Optional[CatalystInfo]:
        """
        Classify a headline into a catalyst tier.
        
        Args:
            headline: News headline text
            
        Returns:
            CatalystInfo if catalyst detected, None otherwise
        """
        headline_lower = headline.lower()
        matches = []
        
        # Check each keyword
        for keyword, type_id in self._keyword_to_type.items():
            if keyword in headline_lower:
                config = self._context.catalyst_types[type_id]
                matches.append((config.get("tier", 5), type_id, keyword))
        
        if not matches:
            return None
        
        # Use highest-priority (lowest tier number) match
        matches.sort(key=lambda x: x[0])
        best_tier, best_type_id, _ = matches[0]
        matched_keywords = [kw for t, tid, kw in matches if tid == best_type_id]
        
        config = self._context.catalyst_types[best_type_id]
        
        return CatalystInfo(
            tier=best_tier,
            type_id=best_type_id,
            type_name=config.get("name", best_type_id),
            keywords_matched=matched_keywords,
            multiplier=config.get("multiplier", 1.0),
            typical_move=config.get("typical_move", "unknown"),
        )
    
    def get_weighted_sentiment(
        self, 
        base_sentiment: float, 
        headline: str
    ) -> tuple[float, Optional[CatalystInfo]]:
        """
        Apply catalyst type weighting to base sentiment score.
        
        Args:
            base_sentiment: Raw sentiment score (-1 to 1)
            headline: News headline text
            
        Returns:
            (weighted_sentiment, catalyst_info)
        """
        catalyst = self.classify(headline)
        
        if catalyst is None:
            return base_sentiment, None
        
        weighted = base_sentiment * catalyst.multiplier
        
        # Clamp to valid range
        thresholds = self._context.thresholds
        max_score = thresholds.get("max_score", 0.9)
        min_score = thresholds.get("min_score", -0.9)
        weighted = max(min_score, min(max_score, weighted))
        
        return weighted, catalyst


# =============================================================================
# SECTOR TRACKER
# =============================================================================

@dataclass
class SectorMomentum:
    """Information about sector-wide momentum."""
    sector_id: str
    sector_name: str
    stocks_moving: list[str]
    avg_change: float
    is_sector_move: bool
    bonus_score: float


class SectorTracker:
    """Tracks sector-wide momentum for sympathy plays using external context."""
    
    def __init__(self, context: Optional[NewsContext] = None):
        self._context = context or get_context()
        self._build_stock_index()
    
    def _build_stock_index(self) -> None:
        """Build stock to sector lookup."""
        self._stock_to_sector = {}
        
        for sector_id, config in self._context.sectors.items():
            for stock in config.get("stocks", []):
                self._stock_to_sector[stock] = sector_id
    
    def get_sector(self, symbol: str) -> Optional[str]:
        """Get sector ID for a stock symbol."""
        return self._stock_to_sector.get(symbol)
    
    def check_sector_momentum(
        self, 
        symbol: str, 
        stock_changes: dict[str, float]
    ) -> Optional[SectorMomentum]:
        """
        Check if symbol's sector is showing coordinated momentum.
        
        Args:
            symbol: Stock code to check
            stock_changes: Dict of {symbol: daily_change_pct} for sector stocks
            
        Returns:
            SectorMomentum if sector move detected, None otherwise
        """
        sector_id = self.get_sector(symbol)
        if not sector_id:
            return None
        
        config = self._context.sectors[sector_id]
        threshold = config.get("correlation_threshold", 0.02)
        
        # Find stocks moving in same direction
        stocks_moving = []
        changes = []
        
        for stock in config.get("stocks", []):
            if stock in stock_changes:
                change = stock_changes[stock]
                if abs(change) >= threshold:
                    stocks_moving.append(stock)
                    changes.append(change)
        
        if len(stocks_moving) < 2:
            return None
        
        # Check if moving in same direction
        positive = sum(1 for c in changes if c > 0)
        negative = len(changes) - positive
        
        if positive < 2 and negative < 2:
            return None  # Mixed signals
        
        avg_change = sum(changes) / len(changes)
        
        # Calculate bonus score (0 to 0.15)
        bonus = min(0.15, len(stocks_moving) * 0.05)
        
        return SectorMomentum(
            sector_id=sector_id,
            sector_name=config.get("name", sector_id),
            stocks_moving=stocks_moving,
            avg_change=avg_change,
            is_sector_move=True,
            bonus_score=bonus,
        )


# =============================================================================
# NEWS CLIENT
# =============================================================================

class NewsClient:
    """
    News fetching and sentiment analysis.
    
    All context (keywords, thresholds, mappings) loaded from external config.
    """
    
    def __init__(self, api_key: Optional[str] = None, context: Optional[NewsContext] = None):
        """
        Initialize news client.
        
        Args:
            api_key: NewsAPI key (optional, uses env var if not provided)
            context: NewsContext instance (optional, uses singleton if not provided)
        """
        self._api_key = api_key or os.getenv("NEWSAPI_KEY")
        self._context = context or get_context()
        self._classifier = CatalystClassifier(self._context)
        self._sector_tracker = SectorTracker(self._context)
        
        # RSS feed sources for HKEX news
        self._rss_feeds = [
            ("https://www.scmp.com/rss/4/feed", "SCMP Business"),
            ("https://www.hkej.com/rss/feed.xml", "HKEJ"),
        ]
    
    def get_news(
        self, 
        symbol: str, 
        hours: int = 24, 
        limit: int = 5
    ) -> dict:
        """
        Get news for a stock symbol.
        
        Args:
            symbol: Stock code (e.g., "0700")
            hours: Hours to look back
            limit: Maximum articles to return
            
        Returns:
            Dict with news articles and sentiment analysis
        """
        company_name = self._context.get_stock_name(symbol)
        cutoff = datetime.now(HK_TZ) - timedelta(hours=hours)
        
        all_news = []
        
        # Try NewsAPI first
        if self._api_key:
            all_news.extend(self._fetch_newsapi(company_name, symbol, cutoff))
        
        # Supplement with RSS feeds
        for feed_url, source in self._rss_feeds:
            try:
                all_news.extend(self._fetch_rss(feed_url, source, company_name, symbol, cutoff))
            except Exception as e:
                logger.warning(f"RSS fetch failed for {source}: {e}")
        
        # Sort by date and limit
        all_news.sort(key=lambda x: x["published_at"], reverse=True)
        all_news = all_news[:limit]
        
        # Calculate overall sentiment
        if all_news:
            scores = [item["sentiment_score"] for item in all_news]
            overall = sum(scores) / len(scores)
        else:
            overall = 0.0
        
        return {
            "symbol": symbol,
            "company_name": company_name,
            "news_count": len(all_news),
            "overall_sentiment": round(overall, 2),
            "sentiment_label": self._sentiment_label(overall),
            "news": all_news,
            "context_version": self._context.version,
        }
    
    def get_news_with_catalyst(
        self, 
        symbol: str, 
        hours: int = 24, 
        limit: int = 5
    ) -> dict:
        """
        Get news with catalyst classification.
        
        Returns news with catalyst type information for better decision making.
        """
        news = self.get_news(symbol, hours=hours, limit=limit)
        
        for item in news.get("news", []):
            headline = item.get("headline", "")
            catalyst = self._classifier.classify(headline)
            
            if catalyst:
                item["catalyst"] = {
                    "type": catalyst.type_name,
                    "tier": catalyst.tier,
                    "multiplier": catalyst.multiplier,
                    "keywords": catalyst.keywords_matched,
                    "typical_move": catalyst.typical_move,
                }
            else:
                item["catalyst"] = None
        
        return news
    
    def has_catalyst(self, symbol: str, hours: int = 24) -> tuple[bool, str]:
        """
        Check if symbol has a news catalyst.
        
        Args:
            symbol: Stock code
            hours: Hours to look back
            
        Returns:
            (has_catalyst, reason)
        """
        news = self.get_news_with_catalyst(symbol, hours=hours, limit=5)
        
        if news["news_count"] == 0:
            return False, "No recent news found"
        
        threshold = self._context.thresholds.get("catalyst_minimum", 0.3)
        
        if news["overall_sentiment"] < threshold:
            return False, f"Sentiment too low ({news['overall_sentiment']:.2f})"
        
        # Find best catalyst
        best_catalyst = None
        for item in news.get("news", []):
            if item.get("catalyst"):
                if best_catalyst is None or item["catalyst"]["tier"] < best_catalyst["tier"]:
                    best_catalyst = item["catalyst"]
                    best_headline = item["headline"]
        
        if best_catalyst:
            return True, f"{best_catalyst['type']}: {best_headline[:50]}..."
        
        # Has positive news but no classified catalyst
        top_headline = news["news"][0]["headline"] if news["news"] else ""
        return True, f"Positive news: {top_headline[:50]}..."
    
    def check_sector_momentum(
        self, 
        symbol: str, 
        stock_changes: dict[str, float]
    ) -> Optional[SectorMomentum]:
        """
        Check if symbol's sector is showing coordinated momentum.
        
        Delegates to SectorTracker.
        """
        return self._sector_tracker.check_sector_momentum(symbol, stock_changes)
    
    def _fetch_newsapi(
        self, 
        company_name: str, 
        symbol: str, 
        cutoff: datetime
    ) -> list[dict]:
        """Fetch news from NewsAPI."""
        if not self._api_key:
            return []
        
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": f'"{company_name}" OR "{symbol}.HK"',
                "apiKey": self._api_key,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 10,
            }
            
            with httpx.Client(timeout=10) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            items = []
            for article in data.get("articles", []):
                pub_date = datetime.fromisoformat(
                    article["publishedAt"].replace("Z", "+00:00")
                )
                
                if pub_date < cutoff:
                    continue
                
                headline = article.get("title", "")
                content = headline + " " + (article.get("description") or "")
                
                items.append({
                    "headline": headline,
                    "source": article.get("source", {}).get("name", "NewsAPI"),
                    "url": article.get("url", ""),
                    "published_at": pub_date.isoformat(),
                    "sentiment_score": self._analyze_sentiment(content),
                    "summary": (article.get("description") or "")[:200],
                })
            
            return items
            
        except Exception as e:
            logger.warning(f"NewsAPI fetch failed: {e}")
            return []
    
    def _fetch_rss(
        self, 
        feed_url: str, 
        source: str, 
        company_name: str, 
        symbol: str, 
        cutoff: datetime
    ) -> list[dict]:
        """Fetch and parse RSS feed."""
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(feed_url)
                response.raise_for_status()
                xml_content = response.text
            
            return self._parse_rss(xml_content, source, company_name, symbol, cutoff)
            
        except Exception as e:
            logger.warning(f"RSS fetch failed for {source}: {e}")
            return []
    
    def _parse_rss(
        self, 
        xml_content: str, 
        source: str, 
        company_name: str, 
        symbol: str, 
        cutoff: datetime
    ) -> list[dict]:
        """Parse RSS XML content."""
        items = []
        
        # Simple regex-based XML parsing
        item_pattern = re.compile(r"<item>(.*?)</item>", re.DOTALL)
        title_pattern = re.compile(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>")
        link_pattern = re.compile(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>")
        pubdate_pattern = re.compile(r"<pubDate>(.*?)</pubDate>")
        desc_pattern = re.compile(
            r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", re.DOTALL
        )
        
        for item_match in item_pattern.finditer(xml_content):
            item_xml = item_match.group(1)
            
            title_match = title_pattern.search(item_xml)
            link_match = link_pattern.search(item_xml)
            pubdate_match = pubdate_pattern.search(item_xml)
            desc_match = desc_pattern.search(item_xml)
            
            if not title_match:
                continue
            
            headline = title_match.group(1).strip()
            
            # Filter for relevant news
            search_terms = [company_name.lower(), symbol]
            content = (headline + " " + (desc_match.group(1) if desc_match else "")).lower()
            
            if not any(term.lower() in content for term in search_terms):
                continue
            
            # Parse date
            pub_date = datetime.now(HK_TZ)
            if pubdate_match:
                try:
                    from email.utils import parsedate_to_datetime
                    pub_date = parsedate_to_datetime(pubdate_match.group(1))
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=HK_TZ)
                except Exception:
                    pass
            
            if pub_date < cutoff:
                continue
            
            full_content = headline + " " + (desc_match.group(1) if desc_match else "")
            
            items.append({
                "headline": headline,
                "source": source,
                "url": link_match.group(1).strip() if link_match else "",
                "published_at": pub_date.isoformat(),
                "sentiment_score": self._analyze_sentiment(full_content),
                "summary": desc_match.group(1).strip()[:200] if desc_match else None,
            })
        
        return items
    
    def _analyze_sentiment(self, text: str) -> float:
        """
        Analyze sentiment of text with catalyst type weighting.
        
        Returns score from -1 (very negative) to 1 (very positive).
        """
        if not text:
            return 0.0
        
        text_lower = text.lower()
        words = set(re.findall(r"\b\w+\b", text_lower))
        
        # Get keywords from context
        positive_words = self._context.positive_keywords
        negative_words = self._context.negative_keywords
        
        positive_count = len(words & positive_words)
        negative_count = len(words & negative_words)
        
        total = positive_count + negative_count
        if total == 0:
            return 0.0
        
        # Base score from -1 to 1
        base_score = (positive_count - negative_count) / total
        
        # Get thresholds from context
        thresholds = self._context.thresholds
        max_score = thresholds.get("max_score", 0.9)
        min_score = thresholds.get("min_score", -0.9)
        base_score = max(min_score, min(max_score, base_score))
        
        # Apply catalyst type weighting
        weighted_score, _ = self._classifier.get_weighted_sentiment(base_score, text)
        
        return round(weighted_score, 2)
    
    def _sentiment_label(self, score: float) -> str:
        """Convert sentiment score to label using context thresholds."""
        thresholds = self._context.thresholds
        
        if score >= thresholds.get("strong_positive", 0.5):
            return "strong_positive"
        elif score >= thresholds.get("positive", 0.3):
            return "positive"
        elif score <= thresholds.get("strong_negative", -0.5):
            return "strong_negative"
        elif score <= thresholds.get("negative", -0.3):
            return "negative"
        else:
            return "neutral"


# =============================================================================
# SINGLETON FACTORY
# =============================================================================

_news_client: Optional[NewsClient] = None


def get_news_client(api_key: Optional[str] = None) -> NewsClient:
    """Get or create news client singleton."""
    global _news_client
    if _news_client is None:
        _news_client = NewsClient(api_key)
    return _news_client


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    """Test the news client with sample headlines."""
    
    print("=" * 60)
    print("NEWS CONTEXT TEST")
    print("=" * 60)
    
    # Load context
    ctx = get_context()
    print(f"\nContext version: {ctx.version}")
    print(f"Positive keywords: {len(ctx.positive_keywords)}")
    print(f"Negative keywords: {len(ctx.negative_keywords)}")
    print(f"Catalyst types: {list(ctx.catalyst_types.keys())}")
    print(f"Sectors: {list(ctx.sectors.keys())}")
    
    # Test sentiment analysis
    print("\n" + "=" * 60)
    print("SENTIMENT ANALYSIS TEST")
    print("=" * 60)
    
    client = NewsClient()
    
    test_headlines = [
        ("Pop Mart announces HK$251M share buyback", "Expected: positive, corporate_action"),
        ("MiniMax IPO debuts on HKEX with strong demand", "Expected: positive, corporate_action"),
        ("Vanke bondholders approve 60% principal extension", "Expected: positive, binary_event"),
        ("Li Auto benefits from EV subsidy extension", "Expected: positive, policy"),
        ("Goldman upgrades Alibaba to overweight", "Expected: positive, analyst"),
        ("Company reports quarterly loss amid weak demand", "Expected: negative"),
        ("Markets trade flat on mixed signals", "Expected: neutral"),
    ]
    
    classifier = CatalystClassifier()
    
    for headline, expected in test_headlines:
        score = client._analyze_sentiment(headline)
        catalyst = classifier.classify(headline)
        catalyst_info = f"{catalyst.type_name} (Tier {catalyst.tier}, {catalyst.multiplier}x)" if catalyst else "None"
        
        print(f"\n{headline[:50]}...")
        print(f"  Sentiment: {score:+.2f}")
        print(f"  Catalyst: {catalyst_info}")
        print(f"  {expected}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
