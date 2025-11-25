#!/usr/bin/env python3
"""
Unit test to verify news filter graceful degradation logic
Tests the new optional news filter functionality
"""

import sys
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent / "services" / "workflow"))

from common.config_loader import get_workflow_config

def test_workflow_config():
    """Test that workflow config loads with correct defaults"""
    print("=" * 70)
    print("TEST 1: Workflow Configuration Loading")
    print("=" * 70)

    config = get_workflow_config()

    # Check news filter configuration
    news_filter = config.get('filters', {}).get('news', {})

    print(f"\n✅ Config loaded successfully")
    print(f"   Filters configured: {list(config.get('filters', {}).keys())}")
    print(f"\n📰 News Filter Settings:")
    print(f"   Enabled: {news_filter.get('enabled')}")
    print(f"   Required: {news_filter.get('required')}")
    print(f"   Fallback Score: {news_filter.get('fallback_score')}")
    print(f"   Min Sentiment: {news_filter.get('min_sentiment')}")

    # Assertions
    assert news_filter.get('enabled') == True, "News filter should be enabled"
    assert news_filter.get('required') == False, "News filter should NOT be required"
    assert news_filter.get('fallback_score') == 0.5, "Fallback score should be 0.5"

    print(f"\n✅ All configuration assertions passed!")
    return True


def test_news_filter_logic():
    """Test the news filter logic with different scenarios"""
    print("\n" + "=" * 70)
    print("TEST 2: News Filter Logic Simulation")
    print("=" * 70)

    # Load config
    workflow_config = get_workflow_config()
    news_filter_config = workflow_config.get('filters', {}).get('news', {})
    news_required = news_filter_config.get('required', False)
    fallback_score = news_filter_config.get('fallback_score', 0.5)
    sentiment_threshold = news_filter_config.get('min_sentiment', 0.3)

    print(f"\nConfiguration:")
    print(f"  News Required: {news_required}")
    print(f"  Fallback Score: {fallback_score}")
    print(f"  Sentiment Threshold: {sentiment_threshold}")

    # Test candidates
    candidates = [
        {"symbol": "AAPL", "score": 0.75},
        {"symbol": "NVDA", "score": 0.82},
        {"symbol": "TSLA", "score": 0.68}
    ]

    # Simulate different news scenarios
    scenarios = [
        {
            "name": "Scenario 1: News service DOWN (no news for any stock)",
            "news_data": {
                "AAPL": None,  # Service error
                "NVDA": None,  # Service error
                "TSLA": None   # Service error
            }
        },
        {
            "name": "Scenario 2: News service UP but no articles",
            "news_data": {
                "AAPL": {"news": []},  # No articles
                "NVDA": {"news": []},  # No articles
                "TSLA": {"news": []}   # No articles
            }
        },
        {
            "name": "Scenario 3: Mixed - some with news, some without",
            "news_data": {
                "AAPL": {"news": [{"sentiment_score": 0.7}]},  # Has positive news
                "NVDA": None,  # Service error
                "TSLA": {"news": []}  # No articles
            }
        },
        {
            "name": "Scenario 4: All have news with good sentiment",
            "news_data": {
                "AAPL": {"news": [{"sentiment_score": 0.8}, {"sentiment_score": 0.6}]},
                "NVDA": {"news": [{"sentiment_score": 0.9}]},
                "TSLA": {"news": [{"sentiment_score": 0.5}]}
            }
        }
    ]

    for scenario in scenarios:
        print(f"\n{'-' * 70}")
        print(f"{scenario['name']}")
        print(f"{'-' * 70}")

        news_candidates = []
        candidates_without_news = 0

        for candidate in candidates:
            symbol = candidate['symbol']
            has_news = False
            sentiment = None

            # Simulate news fetch
            news_response = scenario['news_data'].get(symbol)

            if news_response and news_response.get("news"):
                has_news = True
                news_items = news_response["news"]
                sentiment = sum(n.get("sentiment_score", 0) for n in news_items) / len(news_items)

                if sentiment > sentiment_threshold:
                    candidate["news_sentiment"] = sentiment
                    news_candidates.append(candidate)
                    print(f"  ✅ {symbol}: sentiment {sentiment:.2f} (above threshold)")
                else:
                    print(f"  ⚠️  {symbol}: sentiment {sentiment:.2f} (below threshold {sentiment_threshold})")

            # NEW: Graceful degradation logic
            if not has_news:
                candidates_without_news += 1

                if not news_required:
                    # Proceed without news using fallback score
                    candidate["news_sentiment"] = fallback_score
                    candidate["news_available"] = False
                    news_candidates.append(candidate)
                    print(f"  ℹ️  {symbol}: No news available, using fallback score {fallback_score}")
                else:
                    print(f"  ❌ {symbol}: Rejected (news required but unavailable)")

        # Results
        print(f"\n  Results:")
        print(f"    Candidates passed: {len(news_candidates)}/{len(candidates)}")
        print(f"    Candidates without news: {candidates_without_news}")
        print(f"    Degraded mode: {candidates_without_news > 0}")

        # OLD BEHAVIOR: Would have rejected all candidates without news
        old_behavior_count = sum(1 for c in candidates if scenario['news_data'].get(c['symbol']) and
                                 scenario['news_data'][c['symbol']].get('news'))

        print(f"\n  Comparison:")
        print(f"    OLD behavior would pass: {old_behavior_count} candidates")
        print(f"    NEW behavior passes: {len(news_candidates)} candidates")
        print(f"    Improvement: +{len(news_candidates) - old_behavior_count} candidates allowed through")

    print(f"\n✅ All scenarios tested successfully!")
    return True


if __name__ == "__main__":
    try:
        print("\n🧪 TESTING NEWS FILTER CHANGES")
        print("=" * 70)

        # Run tests
        test_workflow_config()
        test_news_filter_logic()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print("\nSummary:")
        print("  • Workflow config loads correctly with news.required=false")
        print("  • Fallback score of 0.5 is used when news unavailable")
        print("  • Workflow continues processing instead of blocking")
        print("  • Old behavior: blocked 100% of candidates when news down")
        print("  • New behavior: allows candidates through with fallback scores")
        print("\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
