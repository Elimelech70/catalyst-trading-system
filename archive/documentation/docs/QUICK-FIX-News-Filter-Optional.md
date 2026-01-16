# Quick Fix: Make News Filter Optional

**Issue**: [ISSUE-001-News-Filter-Blocking-Trades.md](./ISSUE-001-News-Filter-Blocking-Trades.md)
**Requirement**: REQ-1
**Effort**: 2 hours
**Priority**: P0 (Immediate)

---

## Overview

This quick fix allows the workflow coordinator to proceed with trading even when the news service is unavailable or returns no articles. Candidates without news data receive a neutral fallback score instead of being rejected.

---

## Code Changes Required

### 1. Configuration File Update

**File**: `/root/catalyst-trading-system/config/workflow_config.yaml`

**Add** (if file doesn't exist, create it):

```yaml
workflow:
  # Scan frequency in minutes (default: 30)
  scan_frequency_minutes: 30

  # Number of top candidates to execute (default: 3)
  execute_top_n: 3

  # Filter configuration
  filters:
    news:
      # Enable news filtering stage
      enabled: true

      # Require news to proceed (if false, proceeds without news)
      required: false

      # Minimum sentiment score for positive catalysts
      min_sentiment: 0.3

      # Fallback score when no news available (0.0-1.0)
      fallback_score: 0.5

      # Maximum age of news articles in hours
      max_age_hours: 24

    pattern:
      enabled: true
      required: false
      min_confidence: 0.6

    technical:
      enabled: true
      required: false
```

---

### 2. Workflow Coordinator Update

**File**: `/root/catalyst-trading-system/services/workflow/workflow-coordinator.py`

**Changes Required**: Lines 255-284

#### Current Code (BLOCKING):

```python
# ========== STAGE 2: News Filter (100 → 35) ==========
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
                if news_data.get("news"):  # ← BLOCKS when no news
                    sentiment = sum(n.get("sentiment_score", 0) for n in news_data["news"]) / len(news_data["news"])
                    if sentiment > sentiment_threshold:
                        candidate["news_sentiment"] = sentiment
                        news_candidates.append(candidate)
    except:
        continue

    if len(news_candidates) >= config.AFTER_NEWS_FILTER:
        break
```

#### Updated Code (NON-BLOCKING):

```python
# ========== STAGE 2: News Filter (100 → 35) ==========
state.status = WorkflowStatus.FILTERING_NEWS

# Load workflow config for filter settings
workflow_config = get_workflow_config()
news_filter_config = workflow_config.get('filters', {}).get('news', {})
news_enabled = news_filter_config.get('enabled', True)
news_required = news_filter_config.get('required', False)  # ← NEW: Default to optional
fallback_score = news_filter_config.get('fallback_score', 0.5)

logger.info(
    f"[{cycle_id}] Stage 2: Filtering by news catalysts "
    f"(threshold: {sentiment_threshold}, required: {news_required})..."
)

news_candidates = []
candidates_without_news = 0  # ← NEW: Track missing news

for candidate in candidates:
    has_news = False
    sentiment = None

    try:
        async with state.http_session.get(
            f"{config.NEWS_URL}/api/v1/news/{candidate['symbol']}?limit=5"
        ) as resp:
            if resp.status == 200:
                news_data = await resp.json()
                # Check for positive catalysts
                if news_data.get("news"):
                    has_news = True
                    sentiment = sum(
                        n.get("sentiment_score", 0) for n in news_data["news"]
                    ) / len(news_data["news"])

                    if sentiment > sentiment_threshold:
                        candidate["news_sentiment"] = sentiment
                        news_candidates.append(candidate)
                    else:
                        logger.debug(
                            f"[{cycle_id}] {candidate['symbol']}: "
                            f"sentiment {sentiment:.2f} below threshold {sentiment_threshold}"
                        )
    except Exception as e:
        logger.warning(
            f"[{cycle_id}] News fetch failed for {candidate['symbol']}: {e}"
        )

    # ========== NEW: Graceful degradation logic ==========
    if not has_news:
        candidates_without_news += 1

        if not news_required:
            # Proceed without news using fallback score
            candidate["news_sentiment"] = fallback_score
            candidate["news_available"] = False
            news_candidates.append(candidate)

            logger.info(
                f"[{cycle_id}] {candidate['symbol']}: "
                f"No news available, using fallback score {fallback_score}"
            )
        else:
            logger.debug(
                f"[{cycle_id}] {candidate['symbol']}: "
                f"Rejected (news required but unavailable)"
            )

    if len(news_candidates) >= config.AFTER_NEWS_FILTER:
        break

# ========== NEW: Log degraded mode warning ==========
if candidates_without_news > 0:
    logger.warning(
        f"[{cycle_id}] News filter: {candidates_without_news}/{len(candidates)} "
        f"candidates had no news data (proceeding with fallback scores)"
    )

workflow_result["stages"]["news"] = {
    "candidates": len(news_candidates),
    "filtered_out": len(candidates) - len(news_candidates),
    "threshold_used": sentiment_threshold,
    "candidates_without_news": candidates_without_news,  # ← NEW
    "degraded_mode": candidates_without_news > 0         # ← NEW
}
logger.info(f"[{cycle_id}] News filter: {len(news_candidates)} candidates remain")
```

---

### 3. Config Loader Update

**File**: `/root/catalyst-trading-system/services/workflow/common/config_loader.py`

**Add** this function if it doesn't exist:

```python
def get_workflow_config() -> Dict:
    """
    Load workflow configuration from YAML file.

    Returns:
        Dict: Workflow configuration with defaults

    Default workflow config:
    {
        "scan_frequency_minutes": 30,
        "execute_top_n": 3,
        "filters": {
            "news": {
                "enabled": true,
                "required": false,
                "min_sentiment": 0.3,
                "fallback_score": 0.5,
                "max_age_hours": 24
            },
            "pattern": {
                "enabled": true,
                "required": false,
                "min_confidence": 0.6
            },
            "technical": {
                "enabled": true,
                "required": false
            }
        }
    }
    """
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "workflow_config.yaml"

    # Default configuration
    default_config = {
        "scan_frequency_minutes": 30,
        "execute_top_n": 3,
        "filters": {
            "news": {
                "enabled": True,
                "required": False,  # ← Don't block workflow if news unavailable
                "min_sentiment": 0.3,
                "fallback_score": 0.5,
                "max_age_hours": 24
            },
            "pattern": {
                "enabled": True,
                "required": False,
                "min_confidence": 0.6
            },
            "technical": {
                "enabled": True,
                "required": False
            }
        }
    }

    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                loaded_config = yaml.safe_load(f) or {}

            # Merge with defaults (loaded values override defaults)
            config = {**default_config, **loaded_config.get('workflow', {})}

            # Deep merge filters
            if 'filters' in loaded_config.get('workflow', {}):
                for filter_type, filter_config in loaded_config['workflow']['filters'].items():
                    if filter_type in config['filters']:
                        config['filters'][filter_type].update(filter_config)
                    else:
                        config['filters'][filter_type] = filter_config

            return config
        else:
            logger.warning(f"Workflow config not found at {config_path}, using defaults")
            return default_config

    except Exception as e:
        logger.error(f"Failed to load workflow config: {e}, using defaults")
        return default_config
```

**Update exports** at bottom of file:

```python
__all__ = [
    'get_trading_config',
    'get_risk_config',
    'get_workflow_config',  # ← ADD THIS
    'is_autonomous_mode'
]
```

---

### 4. Import Statement Update

**File**: `/root/catalyst-trading-system/services/workflow/workflow-coordinator.py`

**Update imports** (lines 60-70):

```python
# Import common utilities
from common.config_loader import (
    get_trading_config,
    get_risk_config,
    get_workflow_config,  # ← ADD THIS
    is_autonomous_mode
)
```

---

## Testing

### Manual Testing Steps

1. **Test with news service DOWN**:
```bash
# Stop news service
docker compose stop news

# Trigger workflow
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal", "max_positions": 3}'

# Verify: Workflow should complete with candidates having fallback scores
```

2. **Test with news service UP but no articles**:
```bash
# Start news service
docker compose start news

# Trigger workflow during pre-market hours (no news)
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal", "max_positions": 3}'

# Verify: Candidates without news get fallback_score = 0.5
```

3. **Test with news service UP and articles available**:
```bash
# Trigger workflow during market hours
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal", "max_positions": 3}'

# Verify: Candidates with news get actual sentiment scores
```

### Expected Log Output

**With news available**:
```
[cycle_20251125_123456] Stage 2: Filtering by news catalysts (threshold: 0.3, required: False)...
[cycle_20251125_123456] NVDA: sentiment 0.75 (positive news found)
[cycle_20251125_123456] AAPL: sentiment 0.45 (positive news found)
[cycle_20251125_123456] News filter: 2 candidates remain
```

**Without news (degraded mode)**:
```
[cycle_20251125_123456] Stage 2: Filtering by news catalysts (threshold: 0.3, required: False)...
[cycle_20251125_123456] NVDA: No news available, using fallback score 0.5
[cycle_20251125_123456] AAPL: No news available, using fallback score 0.5
WARNING: News filter: 2/3 candidates had no news data (proceeding with fallback scores)
[cycle_20251125_123456] News filter: 2 candidates remain (degraded mode)
```

---

## Validation Checklist

- [ ] Created `config/workflow_config.yaml` with filter settings
- [ ] Updated `workflow-coordinator.py` lines 255-284
- [ ] Added `get_workflow_config()` to `common/config_loader.py`
- [ ] Updated imports in `workflow-coordinator.py`
- [ ] Tested with news service DOWN (workflow proceeds)
- [ ] Tested with news service UP but no articles (fallback scores used)
- [ ] Tested with news service UP with articles (normal operation)
- [ ] Verified logs show degraded mode warnings
- [ ] Verified workflow completes successfully in all cases
- [ ] Verified at least 1 trade executed in test cycle
- [ ] Updated documentation

---

## Rollback Plan

If this change causes issues:

1. **Immediate rollback**:
```yaml
# config/workflow_config.yaml
workflow:
  filters:
    news:
      required: true  # ← Change back to true
```

2. **Code rollback**:
```bash
git revert <commit_hash>
docker compose restart workflow
```

---

## Post-Implementation

### Monitoring

Watch these metrics for 24 hours:

```bash
# Check workflow completion rate
docker compose logs workflow | grep "Workflow complete"

# Check degraded mode frequency
docker compose logs workflow | grep "degraded mode"

# Check trade execution rate
docker compose logs trading | grep "Position created"
```

### Expected Behavior

- **First cycle**: Should execute at least 1 trade
- **Degraded mode**: Should occur during pre-market hours
- **Normal mode**: Should occur during market hours with news
- **Service failures**: Workflow continues (doesn't block)

---

## Next Steps

After this quick fix is deployed:

1. **REQ-2**: Implement service health checks
2. **REQ-3**: Configure news API keys properly
3. **REQ-4**: Implement full graceful degradation logic
4. **Monitor**: Track degraded mode frequency
5. **Tune**: Adjust fallback_score based on backtesting

---

**Estimated Time to Implement**: 2 hours
**Estimated Time to Test**: 1 hour
**Total Time**: 3 hours

**Risk Level**: Low (makes system more permissive, doesn't break existing functionality)
**Impact**: High (enables trading when news unavailable)
