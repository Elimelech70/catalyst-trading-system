# ISSUE-001: News Filter Blocking Trade Execution

**Status**: Open
**Priority**: High
**Component**: Workflow Coordinator (workflow-service.py)
**First Observed**: Cycle 20251016-001 (October 16, 2025)
**Impact**: No trades executed despite valid candidates identified

---

## Executive Summary

The first trading cycle successfully identified 3 high-quality candidates (NVDA, AAPL, TSLA) with composite scores ranging from 0.44 to 0.67, but **zero trades were executed** due to a mandatory news sentiment filter that rejected all candidates for having no news articles.

The workflow coordinator implements a strict 6-stage pipeline where failure at any stage prevents progression. All candidates failed at Stage 2 (News Filter) and never reached trading execution.

---

## Problem Statement

### What Happened

**Cycle**: `20251016-001`
**Date**: October 16, 2025 at 10:16:18 UTC (6:16 AM ET)
**Duration**: ~1 second
**Scanner Results**: 3 candidates selected
**Trades Executed**: 0

### Scan Results (Stage 1 - Successful)

| Rank | Symbol | Composite Score | Momentum | Volume | Catalyst | Technical | Price | Volume (shares) |
|------|--------|----------------|----------|--------|----------|-----------|-------|-----------------|
| 1 | NVDA | 0.67 | 0.66 | 1.00 | 0.30 | 0.83 | $179.83 | 204.9M |
| 2 | AAPL | 0.50 | 0.19 | 1.00 | 0.30 | 0.59 | $249.34 | 41.6M |
| 3 | TSLA | 0.44 | 0.01 | 1.00 | 0.30 | 0.50 | $435.15 | 81.0M |

**Status**: All 3 marked as `selected_for_trading: true` ✓

### News Filter Results (Stage 2 - Failed)

```json
NVDA: {"news_count": 0, "change_percent": -6.62}
AAPL: {"news_count": 0, "change_percent": -1.85}
TSLA: {"news_count": 0, "change_percent": -0.09}
```

**Result**: 0 candidates advanced to Stage 3
**Reason**: All stocks had `news_count: 0`

---

## Root Cause Analysis

### Technical Root Cause

**File**: `/root/catalyst-trading-system/services/workflow/workflow-coordinator.py`
**Lines**: 255-284

```python
# Stage 2: News Filter (100 → 35)
state.status = WorkflowStatus.FILTERING_NEWS
logger.info(f"[{cycle_id}] Stage 2: Filtering by news catalysts (threshold: {sentiment_threshold})...")

news_candidates = []
for candidate in candidates:
    try:
        async with state.http_session.get(
            f"{config.NEWS_URL}/api/v1/news/{candidate['symbol']}?limit=5"
        ) as resp:
            if resp.status == 200:
                news_data = await resp.json()
                # Check for positive catalysts
                if news_data.get("news"):  # ← BLOCKER: Returns False when no news
                    sentiment = sum(n.get("sentiment_score", 0) for n in news_data["news"]) / len(news_data["news"])
                    if sentiment > sentiment_threshold:  # ← Threshold: 0.3 (normal mode)
                        candidate["news_sentiment"] = sentiment
                        news_candidates.append(candidate)
    except:
        continue

    if len(news_candidates) >= config.AFTER_NEWS_FILTER:
        break
```

### Why No News Articles?

**Possible Causes**:

1. **News Service Not Running**: Port 5008 not accessible
2. **API Keys Missing**: NewsAPI/Benzinga credentials not configured
3. **Early Morning Timing**: 6:16 AM ET - news providers may not have published yet
4. **API Rate Limits**: Free tier NewsAPI has limits (100 requests/day)
5. **Service Error**: News service failing silently (returns empty list)

### Contributing Factors

1. **Market Timing**: 6:16 AM ET (before market open at 9:30 AM)
2. **Negative Price Action**: All stocks were down that day
3. **Test Cycle**: 1-second duration suggests automated test run
4. **Strict Filter**: No fallback mechanism when news unavailable

---

## Impact Assessment

### Current State

- **Blocker Severity**: Critical
- **Affects**: 100% of trading cycles if news service unavailable
- **Business Impact**: Zero trades executed = zero revenue opportunity
- **Risk**: System appears functional but silently fails to trade

### Workflow Pipeline Breakdown

```
Scanner (Stage 1)     ✅ 100 candidates → 3 selected
    ↓
News Filter (Stage 2) ❌ 3 candidates → 0 advanced  ← BLOCKER
    ↓
Pattern Analysis      ⏭️ Never reached
    ↓
Technical Analysis    ⏭️ Never reached
    ↓
Risk Validation       ⏭️ Never reached
    ↓
Trading Execution     ⏭️ Never reached
```

---

## Requirements to Fix

### REQ-1: Make News Filter Optional (Quick Fix)

**Priority**: P0 (Immediate)
**Effort**: 2 hours

Allow workflow to proceed when news is unavailable.

**Acceptance Criteria**:
- [ ] Add `require_news_sentiment: bool` parameter to workflow config
- [ ] Default to `false` for backward compatibility
- [ ] When `false`, candidates with no news get neutral score (0.5)
- [ ] Log warning when proceeding without news data
- [ ] Update workflow documentation

**Config Change** (`config/workflow_config.yaml`):
```yaml
workflow:
  filters:
    news:
      enabled: true
      required: false  # ← NEW: Don't block if unavailable
      min_sentiment: 0.3
      fallback_score: 0.5  # ← NEW: Score when no news
```

### REQ-2: Implement News Service Health Check (Critical)

**Priority**: P0 (Immediate)
**Effort**: 4 hours

Detect news service failures before starting workflow.

**Acceptance Criteria**:
- [ ] Add `/health` endpoint check before workflow starts
- [ ] Workflow startup validates all required services are healthy
- [ ] Return 503 with clear error if news service unavailable
- [ ] Include service health in workflow status response
- [ ] Add service dependency diagram to docs

**Implementation** (`workflow-coordinator.py`):
```python
async def validate_services():
    """Check all required services before starting workflow"""
    services = {
        "scanner": config.SCANNER_URL,
        "news": config.NEWS_URL,
        "pattern": config.PATTERN_URL,
        "technical": config.TECHNICAL_URL,
        "risk": config.RISK_URL,
        "trading": config.TRADING_URL
    }

    unhealthy = []
    for name, url in services.items():
        try:
            async with state.http_session.get(f"{url}/health", timeout=5) as resp:
                if resp.status != 200:
                    unhealthy.append(name)
        except:
            unhealthy.append(name)

    if unhealthy:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Required services unavailable",
                "unhealthy_services": unhealthy,
                "message": f"Cannot start workflow: {', '.join(unhealthy)} not responding"
            }
        )
```

### REQ-3: Configure News API Keys (Environment Setup)

**Priority**: P0 (Immediate)
**Effort**: 1 hour

Ensure news service can fetch data.

**Acceptance Criteria**:
- [ ] Add valid NewsAPI key to `.env`
- [ ] (Optional) Add Benzinga API key to `.env`
- [ ] Verify news service can fetch articles
- [ ] Test with 5 different symbols
- [ ] Document API setup in README

**Environment Variables** (`.env`):
```bash
# News API Configuration
NEWS_API_KEY=your_newsapi_key_here
NEWS_API_ENABLED=true
BENZINGA_API_KEY=your_benzinga_key_here  # Optional
BENZINGA_ENABLED=false

# News Service
NEWS_URL=http://news:5008
```

### REQ-4: Add Graceful Degradation Logic (Medium-term)

**Priority**: P1 (High)
**Effort**: 8 hours

Allow workflow to continue with reduced confidence when services fail.

**Acceptance Criteria**:
- [ ] Assign weighted scores based on available data sources
- [ ] Document score calculation with/without news
- [ ] Add confidence level to each candidate
- [ ] Risk manager considers confidence in position sizing
- [ ] Alert when trading with degraded data

**Score Weighting**:
```python
# Full data available
composite_score = (
    momentum * 0.30 +
    volume * 0.20 +
    news_sentiment * 0.30 +  # ← May be unavailable
    technical * 0.20
)

# Degraded mode (no news)
composite_score = (
    momentum * 0.40 +  # ← Increased weight
    volume * 0.25 +
    technical * 0.35   # ← Increased weight
)
confidence_level = 0.7  # Reduced from 1.0
```

### REQ-5: Implement Service Circuit Breaker (Long-term)

**Priority**: P2 (Medium)
**Effort**: 16 hours

Prevent cascading failures and enable faster recovery.

**Acceptance Criteria**:
- [ ] Add circuit breaker pattern for each service call
- [ ] Track failure rates per service
- [ ] Open circuit after 5 consecutive failures
- [ ] Half-open state for recovery testing
- [ ] Metrics dashboard for service health
- [ ] Alert on circuit breaker state changes

**Libraries**: `aiobreaker` or custom implementation

### REQ-6: Add Workflow Retry Logic (Long-term)

**Priority**: P2 (Medium)
**Effort**: 12 hours

Retry failed stages with exponential backoff.

**Acceptance Criteria**:
- [ ] Retry failed service calls up to 3 times
- [ ] Exponential backoff: 1s, 2s, 4s
- [ ] Track retry attempts in workflow metadata
- [ ] Alert on repeated failures
- [ ] Circuit breaker integration

---

## Recommended Implementation Plan

### Phase 1: Immediate Fixes (Week 1)
**Goal**: Enable trading to work today

1. **Day 1**: Implement REQ-1 (Make news filter optional)
2. **Day 2**: Implement REQ-3 (Configure API keys)
3. **Day 3**: Implement REQ-2 (Health checks)
4. **Day 4-5**: Testing and validation

**Success Metric**: At least 1 trade executed in next cycle

### Phase 2: Resilience Improvements (Week 2-3)
**Goal**: Handle failures gracefully

5. **Week 2**: Implement REQ-4 (Graceful degradation)
6. **Week 3**: Implement REQ-5 (Circuit breakers)

**Success Metric**: Workflow continues with 80%+ confidence when news unavailable

### Phase 3: Production Hardening (Week 4)
**Goal**: Production-ready reliability

7. Implement REQ-6 (Retry logic)
8. Add comprehensive logging and monitoring
9. Create runbook for common failures
10. Load testing with service failures

**Success Metric**: 99.5% workflow completion rate under normal conditions

---

## Testing Requirements

### Unit Tests
- [ ] News filter with empty news list
- [ ] News filter with unavailable service
- [ ] Score calculation with missing data
- [ ] Circuit breaker state transitions

### Integration Tests
- [ ] Full workflow with news service down
- [ ] Full workflow with degraded mode
- [ ] Service health check validation
- [ ] Retry logic under load

### End-to-End Tests
- [ ] Complete trading cycle with all services
- [ ] Complete trading cycle with news disabled
- [ ] Recovery after service restart
- [ ] Market hours vs pre-market behavior

---

## Monitoring & Alerts

### Metrics to Track
- `workflow.stage.news_filter.candidates_in`
- `workflow.stage.news_filter.candidates_out`
- `workflow.stage.news_filter.failures`
- `services.news.health_check.status`
- `services.news.response_time_ms`

### Alerts to Configure
- **Critical**: Workflow completes with 0 trades executed
- **Warning**: News service health check fails
- **Info**: Workflow running in degraded mode
- **Info**: Circuit breaker state change

---

## Documentation Updates Required

1. **Architecture Diagram**: Show service dependencies
2. **Configuration Guide**: Document all workflow filter options
3. **Troubleshooting Guide**: Common failure scenarios
4. **API Setup Guide**: How to configure news providers
5. **Runbook**: Service failure response procedures

---

## Open Questions

1. **Q**: Should we allow trading without ANY news data in production?
   **A**: TBD - Risk manager should enforce minimum confidence threshold

2. **Q**: What minimum confidence level is acceptable?
   **A**: TBD - Needs backtesting data

3. **Q**: Should we cache news data to reduce API calls?
   **A**: Yes - REQ-7 (future): Implement Redis caching layer

4. **Q**: How to handle market holidays when no news published?
   **A**: TBD - Need market calendar integration

---

## Success Criteria

**Short-term** (1 week):
- ✅ At least 1 successful trade executed
- ✅ News service health monitored
- ✅ Clear error messages when services fail

**Medium-term** (1 month):
- ✅ 95% workflow completion rate
- ✅ Graceful degradation working
- ✅ All services monitored

**Long-term** (3 months):
- ✅ 99.5% workflow completion rate
- ✅ Circuit breakers prevent cascading failures
- ✅ Automated recovery from transient failures

---

## References

**Related Files**:
- `/root/catalyst-trading-system/services/workflow/workflow-coordinator.py` (lines 255-284)
- `/root/catalyst-trading-system/services/news/news-service.py`
- `/root/catalyst-trading-system/config/trading_config.yaml`

**Database Evidence**:
- Table: `trading_cycles` → cycle_id = '20251016-001'
- Table: `scan_results` → 3 rows with `news_count: 0`
- Table: `positions` → 0 rows for this cycle

**Related Issues**: None yet

---

**Document Version**: 1.0
**Last Updated**: 2025-11-25
**Author**: System Analysis
**Reviewers**: TBD
