# Trading Concepts & Candidate Selection Logic

**Name of Application:** Catalyst Trading System  
**Name of file:** trading-concepts-fundamentals.md  
**Version:** 1.0.0  
**Last Updated:** 2026-01-02  
**Purpose:** Educational reference for trading concepts and candidate selection logic  
**Location:** Documentation/Trading Knowledge/

---

## REVISION HISTORY

**v1.0.0 (2026-01-02)** - Initial creation
- Complete glossary of technical indicators
- Chart pattern definitions with visual examples
- Candidate selection flow documentation
- Tiered entry criteria explanation

---

## Table of Contents

1. [Technical Indicators](#1-technical-indicators)
2. [Chart Patterns](#2-chart-patterns)
3. [Volume Analysis](#3-volume-analysis)
4. [News & Catalysts](#4-news--catalysts)
5. [Risk Management Concepts](#5-risk-management-concepts)
6. [Candidate Selection Flow](#6-candidate-selection-flow)
7. [Tiered Entry System](#7-tiered-entry-system)
8. [Decision Tree](#8-decision-tree)

---

## 1. Technical Indicators

### 1.1 RSI (Relative Strength Index)

**What it is:** A momentum oscillator that measures the speed and magnitude of recent price changes to evaluate overbought or oversold conditions.

**Range:** 0 to 100

**How it's calculated:**
```
RSI = 100 - (100 / (1 + RS))
where RS = Average Gain / Average Loss over N periods (typically 14)
```

**Interpretation:**
| RSI Value | Condition | Trading Implication |
|-----------|-----------|---------------------|
| > 80 | Severely Overbought | High risk of pullback, AVOID buying |
| 70-80 | Overbought | Caution, momentum may be exhausting |
| 50-70 | Bullish | Healthy uptrend, acceptable for entries |
| 40-50 | Neutral | Consolidation, wait for direction |
| 30-40 | Pullback Zone | IDEAL for momentum entries (buying the dip) |
| 20-30 | Oversold | Potential bounce, but could be falling knife |
| < 20 | Severely Oversold | Extreme fear, high risk |

**Our System Uses:**
- Paper trading: Accept RSI 30-75 (wider range for learning)
- Live trading: Prefer RSI 40-70 (optimal momentum zone)
- RSI > 70 applies a 0.5x penalty to candidate scoring

**Visual:**
```
100 ├─────────────────────────── SEVERELY OVERBOUGHT (Avoid)
 80 ├─────────────────────────── Overbought Zone
 70 ├─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ Upper Threshold
    │  ████████████████████████  BULLISH ZONE
 50 ├─────────────────────────── Neutral Line
    │  ████████████████████████  PULLBACK ZONE (Best entries!)
 30 ├─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ Lower Threshold
 20 ├─────────────────────────── Oversold Zone
  0 ├─────────────────────────── SEVERELY OVERSOLD
```

---

### 1.2 MACD (Moving Average Convergence Divergence)

**What it is:** A trend-following momentum indicator showing the relationship between two moving averages of price.

**Components:**
- **MACD Line:** 12-period EMA minus 26-period EMA
- **Signal Line:** 9-period EMA of the MACD Line
- **Histogram:** MACD Line minus Signal Line

**Interpretation:**
| Signal | Meaning |
|--------|---------|
| MACD crosses ABOVE Signal | Bullish signal (buy) |
| MACD crosses BELOW Signal | Bearish signal (sell) |
| Histogram growing | Momentum increasing |
| Histogram shrinking | Momentum fading |
| MACD above zero | Uptrend |
| MACD below zero | Downtrend |

**Visual:**
```
        MACD Line (fast)
           ╱╲
          ╱  ╲         ← Bullish crossover (BUY)
    ─────╳────╲───────── Signal Line (slow)
        ╱      ╲
       ╱        ╲      ← Bearish crossover (SELL)
──────────────────────── Zero Line
```

---

### 1.3 Moving Averages

**What they are:** Smoothed price lines that help identify trend direction.

**Types:**
- **SMA (Simple Moving Average):** Equal weight to all periods
- **EMA (Exponential Moving Average):** More weight to recent prices

**Common Periods:**
| MA | Purpose |
|----|---------|
| 9 EMA | Very short-term momentum |
| 20 SMA | Short-term trend |
| 50 SMA | Medium-term trend |
| 200 SMA | Long-term trend (institutional reference) |

**Trading Signals:**
```
Price above all MAs = Strong uptrend
Price below all MAs = Strong downtrend

Golden Cross: 50 SMA crosses ABOVE 200 SMA = Bullish
Death Cross: 50 SMA crosses BELOW 200 SMA = Bearish
```

---

### 1.4 ATR (Average True Range)

**What it is:** A volatility indicator showing how much an asset typically moves.

**How it's calculated:**
```
True Range = MAX of:
  - Current High minus Current Low
  - |Current High minus Previous Close|
  - |Current Low minus Previous Close|

ATR = Average of True Range over N periods (typically 14)
```

**Uses in Our System:**
- **Stop Loss Placement:** Stop = Entry - (ATR × multiplier)
- **Position Sizing:** Higher ATR = smaller position
- **Volatility Filter:** ATR% > 5% may indicate excessive risk

**Example:**
```
Stock price: $100
ATR: $3 (3%)

Stop Loss = $100 - ($3 × 1.5) = $95.50
This gives the trade "room to breathe" based on normal volatility.
```

---

### 1.5 Bollinger Bands

**What they are:** Volatility bands placed above and below a moving average.

**Components:**
- **Middle Band:** 20-period SMA
- **Upper Band:** Middle + (2 × standard deviation)
- **Lower Band:** Middle - (2 × standard deviation)

**Interpretation:**
| Condition | Meaning |
|-----------|---------|
| Price touches upper band | Potentially overbought |
| Price touches lower band | Potentially oversold |
| Bands narrowing (squeeze) | Low volatility, breakout coming |
| Bands widening | High volatility, trend in progress |

---

### 1.6 Volume Indicators

**Volume Ratio:**
```
Volume Ratio = Current Volume / Average Volume

> 2.0x = Strong interest (institutional activity)
> 1.5x = Good interest (acceptable for entries)
> 1.0x = Normal
< 1.0x = Low interest (avoid)
```

**OBV (On-Balance Volume):**
- Rising OBV with rising price = Healthy trend
- Rising OBV with flat price = Accumulation (bullish)
- Falling OBV with rising price = Distribution (bearish warning)

---

## 2. Chart Patterns

### 2.1 Breakout

**What it is:** Price moves decisively above a resistance level (or below support).

**Visual:**
```
                          ╱ BREAKOUT!
                         ╱
─────────────────────────  ← Resistance Level
    ╱╲    ╱╲    ╱╲   ╱
   ╱  ╲  ╱  ╲  ╱  ╲ ╱
  ╱    ╲╱    ╲╱    ╲
 ╱
```

**Key Characteristics:**
- Price breaks ABOVE resistance with volume
- Volume should be > 1.5x average on breakout
- Previous resistance becomes new support

**Our Rule:** "Within 1% of breakout level" counts as a breakout setup

---

### 2.2 Bull Flag

**What it is:** A continuation pattern where price consolidates in a downward channel after a strong move up.

**Visual:**
```
           │    ╲
           │     ╲  ← Flag (pullback)
    Pole → │      ╲
           │       ╲╱ ← Breakout point
           │      ╱
           │     ╱
           │    ╱
           │   ╱
        ───┴───
```

**Key Characteristics:**
- Strong upward move (the "pole")
- Consolidation pulling back 20-40% of the move
- Volume decreases during flag formation
- Breakout continues in direction of pole

---

### 2.3 ABCD Pattern

**What it is:** A harmonic pattern with four price points creating two equivalent legs.

**Visual:**
```
                    D
                   ╱
                  ╱
            B    ╱
           ╱╲   ╱
          ╱  ╲ ╱
         ╱    C
        ╱
       A

AB ≈ CD (similar length and time)
```

**Trading:**
- Enter at D
- Stop below C
- Target based on AB projection

---

### 2.4 Cup and Handle

**What it is:** A bullish continuation pattern resembling a tea cup.

**Visual:**
```
Rim ─────╮                 ╭───── Rim
          ╲               ╱│
           ╲             ╱ │ Handle
            ╲           ╱  │╲
             ╲    ╱    ╱    │ ╲
              ╲  ╱ ╲  ╱     │  ╲ Breakout
               ╲╱   ╲╱      
            Cup (rounded bottom)
```

**Key Characteristics:**
- U-shaped cup (not V-shaped)
- Handle forms near the rim (small pullback)
- Breakout above the rim triggers entry

---

### 2.5 Ascending Triangle

**What it is:** A bullish pattern with flat resistance and rising support.

**Visual:**
```
────────────────────── Resistance (flat)
    ╱        ╱╲   ╱
   ╱    ╱╲  ╱  ╲ ╱
  ╱    ╱  ╲╱    ╲
 ╱    ╱
╱    ╱ ← Rising support line
```

**Trading:**
- Breakout above resistance = entry
- Higher lows show buying pressure
- Measured move = height of triangle added to breakout

---

### 2.6 Double Bottom

**What it is:** A reversal pattern forming a "W" shape.

**Visual:**
```
╲              ╱╲
 ╲            ╱  ╲ Neckline
  ╲          ╱    ───────────
   ╲   ╱╲   ╱
    ╲ ╱  ╲ ╱
     ╲    ╲
      1st   2nd
     bottom bottom
```

**Key Characteristics:**
- Two roughly equal lows
- Neckline acts as resistance
- Breakout above neckline confirms reversal

---

## 3. Volume Analysis

### 3.1 Volume Confirms Price

**Healthy Trends:**
```
Price UP + Volume UP = Strong (trend confirmed)
Price UP + Volume DOWN = Weak (potential reversal)
Price DOWN + Volume UP = Strong selling (bearish)
Price DOWN + Volume DOWN = Weak selling (potential bounce)
```

### 3.2 Volume Spikes

**Interpretation:**
| Spike Type | Meaning |
|------------|---------|
| High volume at breakout | Confirmation (good) |
| High volume at resistance | Potential reversal |
| High volume at support | Potential bounce |
| Climax volume (extreme) | Exhaustion, trend may end |

### 3.3 Our Volume Requirements

| Tier | Volume Ratio Requirement |
|------|-------------------------|
| Tier 1 (Strong) | > 2.0x average |
| Tier 2 (Good) | > 1.5x average |
| Tier 3 (Learning) | > 1.3x average |
| Pass | < 1.0x (no interest) |

---

## 4. News & Catalysts

### 4.1 What is a Catalyst?

A catalyst is a news event or development that can drive significant price movement.

**Types of Catalysts:**
| Type | Examples | Typical Impact |
|------|----------|----------------|
| Earnings | Beat/miss expectations | 5-20%+ move |
| FDA Decision | Drug approval/rejection | 20-100%+ move |
| Contract | New major customer | 5-15% move |
| Analyst Upgrade | Price target increase | 3-10% move |
| Sector News | Industry-wide development | Variable |
| M&A | Acquisition/merger news | 10-50%+ move |

### 4.2 Sentiment Scoring

Our system scores news sentiment from -1.0 to +1.0:

| Score | Interpretation |
|-------|----------------|
| > 0.5 | Strongly positive |
| 0.2 to 0.5 | Positive |
| 0.0 to 0.2 | Slightly positive |
| 0.0 | Neutral |
| -0.2 to 0.0 | Slightly negative |
| < -0.2 | Negative |

### 4.3 Our Catalyst Requirements

| Tier | Catalyst Requirement |
|------|---------------------|
| Tier 1 | Sentiment > 0.2 (clear positive) |
| Tier 2 | Sentiment > 0.0 (any positive) OR strong pattern |
| Tier 3 | Any mention OR sector strength |

---

## 5. Risk Management Concepts

### 5.1 Risk/Reward Ratio

**Formula:**
```
Risk/Reward = (Target Price - Entry) / (Entry - Stop Loss)

Example:
Entry: $100
Stop: $97 (risk = $3)
Target: $109 (reward = $9)

R:R = $9 / $3 = 3:1 (excellent)
```

**Our Requirements:**
| Tier | Minimum R:R |
|------|-------------|
| Tier 1 | 2:1 |
| Tier 2 | 1.5:1 |
| Tier 3 | 1.5:1 |

### 5.2 Position Sizing

**Dollar-Based Sizing:**
```
Position Value = Portfolio × Allocation %
Quantity = Position Value / Stock Price

Example:
Portfolio: $100,000
Allocation: 20%
Stock Price: $50

Position Value = $100,000 × 20% = $20,000
Quantity = $20,000 / $50 = 400 shares
```

### 5.3 Stop Loss Types

| Type | Description | Use Case |
|------|-------------|----------|
| Fixed % | Entry - X% | Simple, predictable |
| ATR-based | Entry - (ATR × N) | Adapts to volatility |
| Pattern-based | Below support/pattern | Technical precision |
| Time stop | Close after N minutes if flat | Avoid dead trades |
| Trailing | Move stop up as price rises | Lock in profits |

---

## 6. Candidate Selection Flow

### 6.1 The Funnel

Our system uses a multi-stage filtering process:

```
┌─────────────────────────────────────────────────────────────┐
│                    UNIVERSE SCAN                            │
│                    (~5000 stocks)                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼ Filter: Price $2-$100, Volume > 500K
┌─────────────────────────────────────────────────────────────┐
│                    MOMENTUM SCAN                            │
│                    (~500 stocks)                            │
│     Filter: Volume > 1.3x avg, Price change > 2%            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼ Top 50 by momentum score
┌─────────────────────────────────────────────────────────────┐
│                 TECHNICAL ANALYSIS                          │
│                    (~50 stocks)                             │
│     Calculate: RSI, MACD, Support/Resistance                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼ Filter: RSI 30-75, MACD positive
┌─────────────────────────────────────────────────────────────┐
│                  PATTERN DETECTION                          │
│                    (~20 stocks)                             │
│     Scan: Breakout, Bull Flag, ABCD, Cup & Handle           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼ Filter: Has valid pattern OR catalyst
┌─────────────────────────────────────────────────────────────┐
│                   NEWS & CATALYST                           │
│                    (~10 stocks)                             │
│     Check: Recent news, Sentiment score, Sector trends      │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼ Filter: Risk validation passes
┌─────────────────────────────────────────────────────────────┐
│                    RISK CHECK                               │
│                    (~5 stocks)                              │
│     Verify: Position limits, Sector exposure, R:R ratio     │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼ Rank by tier and score
┌─────────────────────────────────────────────────────────────┐
│                   FINAL CANDIDATES                          │
│                    (1-5 trades)                             │
│     Execute: Place orders with stops and targets            │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Scoring Formula

Each candidate receives a composite score:

```python
# Momentum Score (40% weight)
momentum_score = calculate_momentum(price_change, volume_ratio)

# Technical Score (30% weight)
technical_score = calculate_technicals(rsi, macd, ma_alignment)

# Pattern Score (20% weight)
pattern_score = pattern_confidence  # 0.0 to 1.0

# Catalyst Score (10% weight)
catalyst_score = news_sentiment  # -1.0 to 1.0, normalized

# Composite
final_score = (momentum_score × 0.4) + 
              (technical_score × 0.3) + 
              (pattern_score × 0.2) + 
              (catalyst_score × 0.1)

# Apply RSI penalty if overbought
if rsi > 70:
    final_score *= 0.5
```

---

## 7. Tiered Entry System

### 7.1 Why Tiers?

The old AND-based system required ALL conditions:
- Volume > 1.5x ✓
- RSI 40-70 ✓
- Pattern ✓
- Catalyst ✓
- R:R > 2:1 ✓

**Problem:** The probability of ALL conditions simultaneously was very low, resulting in zero trades.

**Solution:** Tiered system allows good-enough setups while maintaining risk management.

### 7.2 Tier Definitions

#### Tier 1 - Strong Setup (Trade Full Size)

**ALL of these must be true:**
- Volume ratio > 2.0x average
- RSI between 30-70
- Clear chart pattern with defined entry
- Positive news catalyst (sentiment > 0.2)
- Risk/reward ratio >= 2:1
- Stop loss <= 5% from entry

```
Confidence: HIGH
Position Size: 100%
Expected Win Rate: 60-70%
```

#### Tier 2 - Good Setup (Trade Full Size)

**These must be true:**
- Volume ratio > 1.5x average
- RSI between 30-75
- Pattern **OR** Catalyst (not both required!)
- Risk/reward ratio >= 1.5:1
- Price within 1% of breakout level counts

```
Confidence: MEDIUM-HIGH
Position Size: 100%
Expected Win Rate: 50-60%
```

#### Tier 3 - Learning Trade (Trade Half Size)

**These must be true:**
- Volume ratio > 1.3x average
- RSI between 25-80 (wider range)
- Strong momentum (price up > 3% today)
- At least one signal: pattern forming, news mention, or sector strength
- Risk/reward ratio >= 1.5:1

```
Confidence: MEDIUM
Position Size: 50%
Expected Win Rate: 40-50%
Purpose: Generate learning data
```

### 7.3 When to PASS (No Trade)

Only skip if:
- RSI > 80 (severely overbought) or < 20 (crash in progress)
- Volume BELOW average (no institutional interest)
- check_risk returns false (exposure limits)
- Already at max positions (5)
- No identifiable stop loss level

---

## 8. Decision Tree

### 8.1 Complete Flow

```
START: Candidate appears in scan
        │
        ▼
┌───────────────────┐
│ Volume > 1.3x ?   │──── NO ────▶ PASS (no interest)
└─────────┬─────────┘
          │ YES
          ▼
┌───────────────────┐
│ RSI < 80 ?        │──── NO ────▶ PASS (overbought)
└─────────┬─────────┘
          │ YES
          ▼
┌───────────────────┐
│ Has stop level?   │──── NO ────▶ PASS (undefined risk)
└─────────┬─────────┘
          │ YES
          ▼
┌───────────────────┐
│ check_risk OK?    │──── NO ────▶ PASS (limits exceeded)
└─────────┬─────────┘
          │ YES
          ▼
┌───────────────────────────────────────────────┐
│              TIER EVALUATION                   │
├───────────────────────────────────────────────┤
│                                               │
│  Volume > 2x AND RSI 30-70 AND Pattern        │
│  AND Catalyst AND R:R >= 2:1 ?                │
│     │                                         │
│     YES ──────▶ TIER 1 (Full Size)            │
│     │                                         │
│     NO                                        │
│     │                                         │
│     ▼                                         │
│  Volume > 1.5x AND RSI 30-75                  │
│  AND (Pattern OR Catalyst) AND R:R >= 1.5:1 ? │
│     │                                         │
│     YES ──────▶ TIER 2 (Full Size)            │
│     │                                         │
│     NO                                        │
│     │                                         │
│     ▼                                         │
│  Volume > 1.3x AND RSI 25-80                  │
│  AND momentum > 3% AND any signal ?           │
│     │                                         │
│     YES ──────▶ TIER 3 (Half Size)            │
│     │                                         │
│     NO ───────▶ PASS (doesn't qualify)        │
│                                               │
└───────────────────────────────────────────────┘
          │
          ▼
┌───────────────────────────────────────────────┐
│               EXECUTE TRADE                    │
├───────────────────────────────────────────────┤
│  1. Calculate position size based on tier     │
│  2. Set entry price (limit order preferred)   │
│  3. Set stop loss based on pattern/ATR        │
│  4. Set profit target based on R:R            │
│  5. Log decision with reasoning               │
│  6. Submit bracket order                      │
└───────────────────────────────────────────────┘
```

### 8.2 Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                 ENTRY DECISION QUICK REFERENCE              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ✅ GO (Tier 1-3):                                          │
│     • Volume above average (1.3x minimum)                   │
│     • RSI not severely overbought (<80)                     │
│     • Has pattern OR catalyst OR strong momentum            │
│     • Risk/reward at least 1.5:1                            │
│     • Stop loss level is clear                              │
│                                                             │
│  ❌ NO GO:                                                   │
│     • RSI > 80 (severely overbought)                        │
│     • Volume below average                                  │
│     • No pattern AND no catalyst AND no momentum            │
│     • Can't define a stop loss                              │
│     • Risk check fails (exposure limits)                    │
│                                                             │
│  📊 TIER DETERMINES SIZE:                                    │
│     • Tier 1: Full position (20-25% of portfolio)           │
│     • Tier 2: Full position (20-25% of portfolio)           │
│     • Tier 3: Half position (10-12.5% of portfolio)         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Appendix A: Indicator Settings

| Indicator | Period | Notes |
|-----------|--------|-------|
| RSI | 14 | Standard |
| MACD | 12, 26, 9 | Standard |
| SMA Short | 9-20 | Momentum |
| SMA Medium | 50 | Trend |
| SMA Long | 200 | Major trend |
| ATR | 14 | Volatility |
| Bollinger | 20, 2σ | Standard |
| Stochastic | 14, 3 | Standard |

---

## Appendix B: Common Mistakes to Avoid

1. **Chasing Extended Moves**
   - Buying RSI > 70 stocks
   - FOMO after big moves

2. **Ignoring Volume**
   - Low volume breakouts often fail
   - Volume confirms institutional interest

3. **No Stop Loss**
   - Every trade MUST have a defined exit
   - "Hope" is not a strategy

4. **Oversizing**
   - One bad trade shouldn't hurt significantly
   - Max 25% per position (paper), 20% (live)

5. **Revenge Trading**
   - After a loss, wait for next valid setup
   - Don't immediately re-enter

---

## Appendix C: Glossary

| Term | Definition |
|------|------------|
| ATR | Average True Range - volatility measure |
| Breakout | Price moving above resistance |
| Catalyst | News event driving price movement |
| EMA | Exponential Moving Average |
| MACD | Moving Average Convergence Divergence |
| R:R | Risk/Reward Ratio |
| RSI | Relative Strength Index |
| SMA | Simple Moving Average |
| Stop Loss | Predetermined exit point to limit loss |
| Support | Price level where buying interest appears |
| Resistance | Price level where selling pressure appears |
| Volume Ratio | Current volume vs average volume |

---

*Document created: 2026-01-02*  
*For: Catalyst Trading System - US & International*  
*Author: Claude Family (Big Bro)*
