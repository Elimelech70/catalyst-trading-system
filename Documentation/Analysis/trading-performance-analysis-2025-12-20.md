# Trading Performance Analysis - December 2025

**Name of Application**: Catalyst Trading System
**Name of file**: trading-performance-analysis-2025-12-20.md
**Version**: 1.0.0
**Last Updated**: 2025-12-20
**Purpose**: Analysis of trading performance and scoring system effectiveness

---

## Executive Summary

Analysis of 135 Alpaca orders (103 filled, 22 expired, 10 canceled) revealed a **critical flaw in the scoring system**: high composite scores correlate with **losses**, not wins. The system is chasing momentum rather than finding good entry points.

**Total Realized P&L: -$3,283.08**

---

## Key Findings

### 1. High Scores = Worse Performance

| Score Category | Trades | Win Rate | Total P&L |
|----------------|--------|----------|-----------|
| High (≥0.75)   | 16     | **25%**  | **-$2,434** |
| Low (<0.70)    | 10     | 20%      | -$960 |

**Conclusion**: The composite score is NOT predictive of success. Higher scores actually led to worse outcomes.

### 2. Momentum = 1.0 is a SELL Signal, Not BUY

The biggest losers all had **momentum_score = 1.00**:

| Symbol | P&L | Momentum | What Happened |
|--------|-----|----------|---------------|
| QUBT | -$1,140 | 1.00 | Bought at top of rally, crashed |
| LYFT | -$536 | 0.71 | Weak momentum, weak trade |
| PATH | -$388 | 1.00 | Bought extended, mean reverted |
| UAMY | -$332 | 1.00 | Bought at top |
| AAOI | -$325 | 1.00 | Bought at top, low volume |
| RGTI | -$269 | 1.00 | Bought at top |

**Root Cause**:
- Momentum = 1.0 means the stock has ALREADY moved significantly
- System interprets "already moved up" as "good to buy"
- This is momentum CHASING, not momentum TRADING

### 3. Rank 4 Outperformed Rank 1

| Rank | Trades | Wins | Win Rate | P&L |
|------|--------|------|----------|-----|
| 1 (highest score) | 9 | 4 | 44% | **-$1,037** |
| 2 | 7 | 1 | 14% | -$711 |
| 3 | 6 | 0 | 0% | -$1,220 |
| **4** | **5** | **3** | **60%** | **+$253** |
| 5 | 5 | 1 | 20% | -$546 |

**Conclusion**: Lower-ranked (less "hot") stocks performed better. The system should be more contrarian.

### 4. Winners vs Losers Profile

| Metric | Winners (9) | Losers (23) |
|--------|-------------|-------------|
| Avg Composite Score | 0.73 | 0.73 |
| Avg Momentum Score | 0.86 | 0.88 |
| Avg Volume Score | 0.98 | 0.95 |
| Avg Technical Score | 0.92 | 0.92 |
| Avg Rank | 2.6 | 2.7 |

**Conclusion**: The scoring metrics are essentially identical for winners and losers. The current scoring system has NO predictive power.

---

## Root Cause Analysis

### Problem 1: Momentum Score Interpretation is Inverted

**Current Logic**:
```
High momentum (1.0) → High score → BUY
```

**Reality**:
```
High momentum (1.0) → Stock already extended → BAD entry → LOSS
```

**Correct Logic**:
```
Moderate momentum (0.4-0.7) → Pullback from highs → GOOD entry → WIN
```

### Problem 2: No Mean Reversion Consideration

The system only looks at:
- Is the stock moving up? (momentum)
- Is there volume? (volume)
- Are technicals positive? (technical)

It does NOT consider:
- How far has it already moved?
- Is it overbought (RSI > 70)?
- Is this a pullback opportunity?

### Problem 3: Volume Spike + Momentum = Late Entry

When both volume AND momentum are 1.0, it typically means:
- News event has already occurred
- Initial move is complete
- Smart money is selling to retail
- Entry is at the TOP, not the bottom

---

## Recommended Fixes

### Fix 1: Penalize Extreme Momentum

**Before** (scanner-service.py):
```python
momentum_score = min(1.0, price_change_5d / 0.10)  # Higher = better
```

**After**:
```python
# Optimal momentum is 0.03-0.07 (3-7% move)
# Penalize both too low (<2%) and too high (>10%)
raw_momentum = price_change_5d
if raw_momentum < 0.02:
    momentum_score = raw_momentum / 0.02 * 0.5  # Weak momentum = low score
elif raw_momentum <= 0.07:
    momentum_score = 0.7 + (raw_momentum - 0.02) / 0.05 * 0.3  # Sweet spot
else:
    # PENALIZE extended stocks
    momentum_score = max(0.3, 1.0 - (raw_momentum - 0.07) / 0.10)
```

### Fix 2: Add RSI Overbought Filter

```python
# Reject if RSI > 70 (overbought)
if rsi > 70:
    technical_score *= 0.5  # Penalize overbought

# Bonus for RSI pullback (40-60 range)
if 40 <= rsi <= 60:
    technical_score *= 1.2  # Reward pullback entries
```

### Fix 3: Add "Days Since Breakout" Penalty

```python
# If stock broke out > 3 days ago, we're late
days_since_breakout = calculate_days_since_breakout(symbol)
if days_since_breakout > 3:
    composite_score *= 0.7  # Late entry penalty
```

### Fix 4: Volume Spike Warning

```python
# If volume is 3x+ average AND momentum is 1.0, this is likely the TOP
if volume_ratio > 3.0 and momentum_score > 0.9:
    composite_score *= 0.5  # Climax volume = danger
```

---

## Implementation Priority

| Priority | Fix | Expected Impact |
|----------|-----|-----------------|
| 1 | Penalize extreme momentum | Avoid -$2,000+ in losses |
| 2 | RSI overbought filter | Prevent buying tops |
| 3 | Volume spike warning | Avoid climax buys |
| 4 | Days since breakout | Better entry timing |

---

## Validation Plan

After implementing fixes:

1. **Paper trade for 1 week** with new scoring
2. **Compare metrics**:
   - Win rate (target: >50%)
   - Average winner vs average loser
   - High score correlation with wins
3. **Adjust thresholds** based on results

---

## Appendix: Trade Data

### Top Winners
| Symbol | Entry | Exit | P&L | Composite | Momentum |
|--------|-------|------|-----|-----------|----------|
| MRNA | $27.70 | ~$29.11 | +$293 | 0.79 | 1.00 |
| AEO | $25.03 | ~$25.38 | +$157 | 0.74 | 0.86 |
| HPE | $23.33 | ~$23.95 | +$155 | 0.66 | 0.63 |
| CCL | $27.84 | ~$28.15 | +$63 | 0.71 | 0.76 |
| UEC | $12.75 | ~$13.33 | +$58 | 0.76 | 1.00 |

### Top Losers
| Symbol | Entry | Exit | P&L | Composite | Momentum |
|--------|-------|------|-----|-----------|----------|
| QUBT | $12.84 | ~$9.42 | -$1,140 | 0.79 | 1.00 |
| LYFT | $22.52 | ~$19.83 | -$536 | 0.69 | 0.71 |
| PATH | $19.21 | ~$17.27 | -$388 | 0.79 | 1.00 |
| UAMY | $6.35 | ~$5.52 | -$332 | 0.79 | 1.00 |
| AAOI | $34.94 | ~$33.32 | -$325 | 0.62 | 1.00 |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-20 | Initial analysis based on Dec 5-15 trades |
