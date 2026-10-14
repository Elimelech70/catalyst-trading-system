"""
Data layer for the Catalyst Trading Agent.

This package provides data access for:
- Database operations (PostgreSQL)
- Market data and technical indicators
- Pattern detection
- News and sentiment analysis
"""

from data.database import DatabaseClient, get_database
from data.market import MarketData, get_market_data
from data.patterns import PatternDetector, get_pattern_detector
from data.news import NewsClient, get_news_client

__all__ = [
    "DatabaseClient",
    "get_database",
    "MarketData",
    "get_market_data",
    "PatternDetector",
    "get_pattern_detector",
    "NewsClient",
    "get_news_client",
]
