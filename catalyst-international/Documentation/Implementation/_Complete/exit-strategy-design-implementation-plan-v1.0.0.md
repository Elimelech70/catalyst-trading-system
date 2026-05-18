# Exit Strategy Design & Implementation Plan
# Context-Separated Architecture

**Name of Application:** Catalyst Trading System  
**Name of file:** exit-strategy-design-implementation-plan-v1.0.0.md  
**Version:** 1.0.0  
**Last Updated:** 2026-01-24  
**Purpose:** Design and implementation plan for intelligent, pattern-based exit strategy with context-separated architecture

---

## REVISION HISTORY

**v1.0.0 (2026-01-24)** - Initial design
- Context-separated architecture (YAML config + pure tool)
- Pattern deterioration detection
- Hold signals for letting winners run
- Market-specific configurations (HKEX/US)
- Haiku AI consultation for borderline decisions

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [Architecture Design](#3-architecture-design)
4. [Exit Context Configuration](#4-exit-context-configuration)
5. [Signal Detection Logic](#5-signal-detection-logic)
6. [Pattern Deterioration Rules](#6-pattern-deterioration-rules)
7. [Hold Conditions](#7-hold-conditions)
8. [Implementation Plan](#8-implementation-plan)
9. [File Specifications](#9-file-specifications)
10. [Testing Strategy](#10-testing-strategy)
11. [Rollback Plan](#11-rollback-plan)

---

## 1. Executive Summary

### Problem Statement

The current exit strategy relies heavily on **static thresholds** (stop loss at -3%, take profit at +8%) embedded directly in the code. This approach:

1. Exits profitable trades too early (doesn't let winners run)
2. Doesn't adapt to pattern health
3. Requires code changes to tune thresholds
4. Can't be A/B tested easily
5. Uses same settings for different market conditions

### Solution

Implement a **context-separated exit strategy** that:

1. **Separates context from tool** - Thresholds and rules live in YAML, logic lives in Python
2. **Detects pattern deterioration** - Exit when the entry pattern breaks, not just on P&L
3. **Includes hold signals** - Recognize when momentum is healthy and let trades run
4. **Supports market-specific tuning** - Different thresholds for HKEX vs US
5. **Enables hot-reload** - Change config without restarting services

### Expected Outcomes

| Metric | Current | Target |
|--------|---------|--------|
| Average losing trade | -3.0% | -1.5% (early pattern exit) |
| Average winning trade | +5.0% | +7.0% (let winners run) |
| Config update process | Edit Python → redeploy | Edit YAML → auto-reload |
| A/B testing capability | None | Swap config files |

---

## 2. Current State Analysis

### Current Implementation

**File:** `signals.py` (both intl_claude and dev_claude)

```python
# CURRENT: Context embedded in tool
class SignalThresholds:
    stop_loss_strong: float = -0.03      # Hardcoded
    stop_loss_moderate: float = -0.02    # Hardcoded
    take_profit_strong: float = 0.08     # Hardcoded
    trailing_stop_pct: float = 0.02      # Hardcoded
    rsi_overbought_strong: float = 85    # Hardcoded
```

### Current Exit Signal Types

| Signal | Trigger | Strength | Issue |
|--------|---------|----------|-------|
| Stop Loss | P&L ≤ -3% | STRONG | Static, doesn't consider pattern health |
| Take Profit | P&L ≥ +8% | STRONG | May exit too early on runners |
| Trailing Stop | 2% from high | MODERATE | Doesn't adapt to volatility |
| RSI Overbought | RSI ≥ 85 | STRONG | Good, but threshold hardcoded |
| Volume Collapse | Vol < 25% entry | STRONG | Good signal, hardcoded |

### What's Missing

| Missing Signal | Description | Impact |
|----------------|-------------|--------|
| **Lower High** | Price making lower highs | Early momentum warning |
| **Pattern Breakdown** | Entry pattern support broken | Entry thesis invalidated |
| **MACD Divergence** | Price up, MACD down | Hidden weakness |
| **EMA Cross Down** | 9 EMA < 20 EMA | Trend reversal |
| **Failed Retest** | Breakout retest fails | Breakout rejected |
| **Higher Lows (HOLD)** | Healthy pullback structure | Let winners run |
| **Volume Confirmation (HOLD)** | Up volume > down volume | Accumulation phase |

---

## 3. Architecture Design

### Core Principle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTEXT-SEPARATED ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   config/                                                                    │
│   └── exit_context.yaml          ← CONTEXT (editable, version-controlled)   │
│       ├── thresholds             ← P&L limits, RSI levels                   │
│       ├── pattern_exit_rules     ← When patterns fail                       │
│       ├── hold_conditions        ← When to let winners run                  │
│       └── market_overrides       ← HKEX vs US specific                      │
│                                                                              │
│   data/                                                                      │
│   └── signals.py                 ← TOOL (pure logic, loads context)         │
│       ├── load_exit_context()    ← Config loader with hot-reload            │
│       ├── detect_exit_signals()  ← Uses context, returns signals            │
│       ├── detect_hold_signals()  ← Recognizes healthy positions             │
│       └── analyze_pattern_health()← Pattern deterioration detection          │
│                                                                              │
│   position_monitor_service.py    ← CONSUMER (uses signals.py)               │
│       └── Calls detect_exit_signals() every 5 minutes                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│                 │      │                 │      │                 │
│  exit_context   │──────│    signals.py   │──────│  position_      │
│    .yaml        │ load │   (pure tool)   │ call │  monitor_       │
│                 │      │                 │      │  service.py     │
└─────────────────┘      └─────────────────┘      └─────────────────┘
     CONTEXT                   TOOL                   CONSUMER
   (editable)              (fixed logic)           (uses signals)
```

### Hot-Reload Mechanism

```python
# signals.py - Context loader with hot-reload
import yaml
from pathlib import Path
from datetime import datetime

_context_cache = None
_context_mtime = None
_context_path = Path("config/exit_context.yaml")

def load_exit_context(force_reload: bool = False) -> dict:
    """Load exit context with automatic hot-reload."""
    global _context_cache, _context_mtime
    
    current_mtime = _context_path.stat().st_mtime
    
    if force_reload or _context_cache is None or current_mtime > _context_mtime:
        with open(_context_path) as f:
            _context_cache = yaml.safe_load(f)
        _context_mtime = current_mtime
        logger.info(f"Loaded exit context v{_context_cache.get('version')}")
    
    return _context_cache
```

---

## 4. Exit Context Configuration

### File: `config/exit_context.yaml`

```yaml
# ============================================================================
# EXIT CONTEXT CONFIGURATION
# ============================================================================
# 
# Name of Application: Catalyst Trading System
# Name of file: exit_context.yaml
# Version: 1.0.0
# Last Updated: 2026-01-24
# Purpose: Configurable exit strategy thresholds and rules
#
# INSTRUCTIONS:
# - Edit this file to tune exit strategy
# - Changes are hot-reloaded (no restart needed)
# - Test changes in paper trading first
# - Commit changes to git for version control
#
# ============================================================================

version: "1.0.0"
last_updated: "2026-01-24"
author: "Craig + Claude"

# ============================================================================
# P&L THRESHOLDS
# ============================================================================
# These control when to exit based on profit/loss percentage

thresholds:
  # Stop Loss - Cut losses early
  stop_loss:
    strong: -0.03        # -3% = IMMEDIATE EXIT
    moderate: -0.02      # -2% = Consult Haiku
    weak: -0.01          # -1% = Monitor closely
  
  # Take Profit - Lock in gains
  take_profit:
    strong: 0.10         # +10% = Consider exit (but check pattern)
    moderate: 0.06       # +6% = Trail stop tighter
    weak: 0.03           # +3% = Healthy, monitor
  
  # Trailing Stop - Protect gains from high
  trailing_stop:
    activation_pct: 0.03   # Activate after +3% profit
    drop_pct: 0.025        # Exit on 2.5% drop from high
  
  # Time Stop - Flat positions
  time_stop:
    minutes_flat: 120      # 2 hours with no movement = re-evaluate

# ============================================================================
# TECHNICAL INDICATOR THRESHOLDS
# ============================================================================

technical:
  rsi:
    overbought_strong: 85    # STRONG exit signal
    overbought_moderate: 75  # MODERATE - consult AI
    oversold_strong: 15      # For shorts: STRONG exit
    oversold_moderate: 25    # For shorts: MODERATE
    healthy_low: 40          # Below this = pullback zone
    healthy_high: 65         # Above this = extended
  
  macd:
    bearish_cross_weight: 0.3  # Weight for MACD bearish cross
    divergence_periods: 5      # Look back periods for divergence
  
  volume:
    collapse_strong: 0.25      # <25% of entry = STRONG exit
    collapse_moderate: 0.40    # <40% of entry = MODERATE
    healthy_min: 0.80          # >80% of entry = healthy
    strong_min: 1.20           # >120% of entry = STRONG hold

  moving_averages:
    ema_fast: 9
    ema_slow: 20
    sma_short: 10
    sma_medium: 20

# ============================================================================
# PATTERN DETERIORATION RULES
# ============================================================================
# When the entry pattern structure breaks

pattern_exit_rules:
  # Lower High Detection
  lower_high:
    enabled: true
    consecutive_required: 2    # 2 consecutive lower highs
    min_drop_pct: 0.005       # 0.5% lower than previous high
    signal_strength: "MODERATE"
    description: "Momentum weakening - price making lower highs"
  
  # Pattern Support Breakdown
  pattern_breakdown:
    enabled: true
    support_break_pct: 0.02   # 2% below pattern support = broken
    signal_strength: "STRONG"
    description: "Entry pattern support violated"
  
  # MACD Bearish Divergence
  macd_divergence:
    enabled: true
    price_higher_high: true    # Price making higher high
    macd_lower_high: true      # But MACD making lower high
    lookback_periods: 5
    signal_strength: "MODERATE"
    description: "Hidden weakness - price up but momentum down"
  
  # EMA Cross Down
  ema_cross_down:
    enabled: true
    fast_period: 9
    slow_period: 20
    signal_strength: "MODERATE"
    description: "Short-term trend reversal"
  
  # Failed Breakout Retest
  failed_retest:
    enabled: true
    retest_tolerance_pct: 0.01  # Within 1% of breakout level
    failure_drop_pct: 0.02      # Then drops 2%
    signal_strength: "STRONG"
    description: "Breakout rejected on retest"
  
  # Consolidation Too Long
  consolidation_stall:
    enabled: true
    max_range_pct: 0.02        # Trading in <2% range
    max_periods: 10            # For 10+ periods
    signal_strength: "WEAK"
    description: "Momentum stalled - sideways too long"

# ============================================================================
# HOLD CONDITIONS
# ============================================================================
# When to let winners run instead of taking profit

hold_conditions:
  # Higher Lows Pattern
  higher_lows:
    enabled: true
    consecutive_required: 2    # 2+ higher lows
    min_rise_pct: 0.005       # Each low 0.5%+ higher
    signal_strength: "STRONG"
    description: "Healthy uptrend structure - accumulation"
  
  # Price Above Key MAs
  above_moving_averages:
    enabled: true
    require_above_ema9: true
    require_above_sma20: true
    signal_strength: "MODERATE"
    description: "Price above key moving averages - trend intact"
  
  # Volume Confirmation
  volume_confirmation:
    enabled: true
    up_volume_ratio: 1.2      # Up candle volume > down candle volume
    lookback_periods: 5
    signal_strength: "MODERATE"
    description: "Buying pressure stronger than selling"
  
  # MACD Histogram Growing
  macd_expansion:
    enabled: true
    growth_periods: 3          # Growing for 3+ periods
    signal_strength: "MODERATE"
    description: "Momentum accelerating"
  
  # RSI in Sweet Spot
  rsi_healthy:
    enabled: true
    min_rsi: 45
    max_rsi: 70
    signal_strength: "WEAK"
    description: "RSI in healthy zone - room to run"
  
  # Above VWAP
  above_vwap:
    enabled: true
    min_above_pct: 0.01       # At least 1% above VWAP
    signal_strength: "MODERATE"
    description: "Trading above average price - bullish"

# ============================================================================
# MARKET-SPECIFIC OVERRIDES
# ============================================================================
# Different settings for different markets

market_overrides:
  hkex:
    # HKEX tends to have wider swings
    thresholds:
      stop_loss:
        strong: -0.035       # -3.5% for HKEX
      take_profit:
        strong: 0.12         # +12% for HKEX
      trailing_stop:
        drop_pct: 0.03       # 3% trailing for HKEX
    
    # HKEX lunch break handling
    time_rules:
      lunch_exit_warning: "11:50"  # HKT
      lunch_start: "12:00"
      lunch_end: "13:00"
      market_close_warning: "15:45"
      market_close: "16:00"
  
  us:
    # US market - tighter stops, no lunch break
    thresholds:
      stop_loss:
        strong: -0.05        # -5% for US (more volatile)
        moderate: -0.03
      take_profit:
        strong: 0.10
      trailing_stop:
        activation_pct: 0.04 # Activate after +4%
        drop_pct: 0.03       # 3% trailing
    
    time_rules:
      market_close_warning: "15:45"  # ET
      market_close: "16:00"
      power_hour_start: "15:00"      # Volatility increases

# ============================================================================
# AI CONSULTATION RULES
# ============================================================================
# When to ask Haiku for exit decision

ai_consultation:
  enabled: true
  model: "claude-3-5-haiku-20241022"
  max_calls_per_position: 10
  cost_per_call: 0.05
  
  # Consult AI when:
  consult_conditions:
    - "MODERATE exit signal detected"
    - "Conflicting signals (exit + hold)"
    - "Near take profit but pattern healthy"
    - "Time stop approaching"
  
  # Don't consult AI when:
  skip_conditions:
    - "STRONG exit signal (exit immediately)"
    - "All STRONG hold signals (keep holding)"
    - "Position < 1 hour old (too early)"

# ============================================================================
# SIGNAL WEIGHTS
# ============================================================================
# For scoring when multiple signals conflict

signal_weights:
  exit_signals:
    stop_loss_hit: 1.0           # Highest priority
    pattern_breakdown: 0.9
    trailing_stop_hit: 0.8
    rsi_overbought: 0.7
    failed_retest: 0.7
    volume_collapse: 0.6
    macd_divergence: 0.5
    lower_high: 0.4
    ema_cross_down: 0.4
    consolidation_stall: 0.2
  
  hold_signals:
    higher_lows: 0.8
    above_moving_averages: 0.6
    volume_confirmation: 0.6
    macd_expansion: 0.5
    above_vwap: 0.4
    rsi_healthy: 0.3

# ============================================================================
# BRACKET ORDER BACKUP
# ============================================================================
# Wide brackets as catastrophic backstop

bracket_orders:
  # These are WIDER than AI monitoring - only hit if AI fails
  stop_loss_pct: -0.08         # -8% catastrophic stop
  take_profit_pct: 0.15        # +15% extreme take profit
  
  # AI should exit BEFORE these trigger
  expected_ai_exit_loss: -0.02  # AI exits at -2%
  expected_ai_exit_gain: 0.08   # AI trails gains

```

---

## 5. Signal Detection Logic

### Updated `signals.py` Structure

```python
"""
Name of Application: Catalyst Trading System
Name of file: signals.py  
Version: 3.0.0
Last Updated: 2026-01-24
Purpose: Context-separated exit signal detection

REVISION HISTORY:
v3.0.0 (2026-01-24) - Context-separated architecture
  - Loads thresholds from exit_context.yaml
  - Added pattern deterioration detection
  - Added hold signal detection
  - Hot-reload capability for context
  
v2.0.0 (2026-01-10) - Added hold signals
v1.0.0 (2026-01-01) - Initial implementation
"""

import yaml
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# CONTEXT LOADER
# ============================================================================

_context_cache: Optional[dict] = None
_context_mtime: Optional[float] = None

def get_context_path() -> Path:
    """Get path to exit context file."""
    # Check multiple locations
    paths = [
        Path("config/exit_context.yaml"),
        Path("/root/catalyst-international/config/exit_context.yaml"),
        Path("/root/catalyst-dev/config/exit_context.yaml"),
    ]
    for p in paths:
        if p.exists():
            return p
    raise FileNotFoundError("exit_context.yaml not found")

def load_exit_context(force_reload: bool = False) -> dict:
    """
    Load exit context with automatic hot-reload.
    
    Checks file modification time and reloads if changed.
    """
    global _context_cache, _context_mtime
    
    context_path = get_context_path()
    current_mtime = context_path.stat().st_mtime
    
    if force_reload or _context_cache is None or current_mtime > _context_mtime:
        with open(context_path) as f:
            _context_cache = yaml.safe_load(f)
        _context_mtime = current_mtime
        logger.info(f"Loaded exit context v{_context_cache.get('version')}")
    
    return _context_cache

def reload_context():
    """Force reload of exit context."""
    return load_exit_context(force_reload=True)

# ============================================================================
# DATA CLASSES
# ============================================================================

class SignalType(Enum):
    EXIT = "exit"
    HOLD = "hold"

class SignalStrength(Enum):
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"

@dataclass
class Signal:
    """Represents a detected signal."""
    name: str
    signal_type: SignalType
    strength: SignalStrength
    reason: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    weight: float = 0.5

@dataclass 
class SignalAnalysis:
    """Complete analysis of a position."""
    exit_signals: List[Signal]
    hold_signals: List[Signal]
    pattern_health: Dict[str, Any]
    recommendation: str  # "EXIT", "HOLD", "CONSULT_AI"
    confidence: float
    
    @property
    def immediate_exit(self) -> bool:
        """Check if any STRONG exit signal."""
        return any(s.strength == SignalStrength.STRONG for s in self.exit_signals)
    
    @property
    def consult_ai(self) -> bool:
        """Check if AI consultation needed."""
        return self.recommendation == "CONSULT_AI"

# ============================================================================
# MAIN DETECTION FUNCTION
# ============================================================================

def analyze_position(
    position: Dict[str, Any],
    quote: Dict[str, Any],
    technicals: Dict[str, Any],
    price_history: Optional[List[Dict]] = None,
    entry_pattern: Optional[Dict] = None,
    market: str = "hkex"
) -> SignalAnalysis:
    """
    Analyze position for exit/hold signals using context configuration.
    
    Args:
        position: Position data (symbol, entry_price, current_price, pnl_pct, etc.)
        quote: Current quote data (price, volume, bid, ask)
        technicals: Technical indicators (rsi, macd, ema9, sma20, vwap, etc.)
        price_history: Recent OHLCV data for pattern analysis
        entry_pattern: Original entry pattern info
        market: "hkex" or "us" for market-specific rules
    
    Returns:
        SignalAnalysis with exit_signals, hold_signals, and recommendation
    """
    context = load_exit_context()
    
    # Apply market-specific overrides
    thresholds = _get_thresholds(context, market)
    
    exit_signals = []
    hold_signals = []
    
    # Extract position data
    pnl_pct = position.get('pnl_pct', 0) or 0
    entry_price = position.get('entry_price', 0) or 0
    current_price = position.get('current_price') or quote.get('price', 0)
    high_watermark = position.get('high_watermark', current_price)
    entry_time = position.get('entry_time')
    entry_volume = position.get('entry_volume', 0)
    
    # === P&L SIGNALS ===
    exit_signals.extend(_detect_pnl_signals(pnl_pct, high_watermark, entry_price, thresholds, context))
    
    # === TECHNICAL SIGNALS ===
    exit_signals.extend(_detect_technical_exit_signals(technicals, context))
    hold_signals.extend(_detect_technical_hold_signals(technicals, current_price, context))
    
    # === VOLUME SIGNALS ===
    current_volume = quote.get('volume', 0)
    if entry_volume and current_volume:
        exit_signals.extend(_detect_volume_exit_signals(current_volume, entry_volume, context))
        hold_signals.extend(_detect_volume_hold_signals(current_volume, entry_volume, context))
    
    # === PATTERN DETERIORATION ===
    if price_history:
        pattern_exits = _detect_pattern_deterioration(price_history, technicals, entry_pattern, context)
        exit_signals.extend(pattern_exits)
    
    # === PATTERN HEALTH (HOLD SIGNALS) ===
    pattern_health = {}
    if price_history:
        pattern_health = _analyze_pattern_health(price_history, technicals, context)
        hold_signals.extend(_pattern_health_to_signals(pattern_health, context))
    
    # === TIME SIGNALS ===
    if entry_time:
        exit_signals.extend(_detect_time_signals(entry_time, pnl_pct, context, market))
    
    # === DETERMINE RECOMMENDATION ===
    recommendation, confidence = _determine_recommendation(exit_signals, hold_signals, context)
    
    return SignalAnalysis(
        exit_signals=exit_signals,
        hold_signals=hold_signals,
        pattern_health=pattern_health,
        recommendation=recommendation,
        confidence=confidence
    )

# ============================================================================
# P&L SIGNAL DETECTION
# ============================================================================

def _detect_pnl_signals(
    pnl_pct: float,
    high_watermark: float,
    entry_price: float,
    thresholds: dict,
    context: dict
) -> List[Signal]:
    """Detect P&L-based exit signals."""
    signals = []
    weights = context.get('signal_weights', {}).get('exit_signals', {})
    
    sl = thresholds['stop_loss']
    tp = thresholds['take_profit']
    ts = thresholds['trailing_stop']
    
    # Stop Loss
    if pnl_pct <= sl['strong']:
        signals.append(Signal(
            name="stop_loss_hit",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            reason=f"Stop loss hit: {pnl_pct*100:.1f}% <= {sl['strong']*100:.1f}%",
            value=pnl_pct,
            threshold=sl['strong'],
            weight=weights.get('stop_loss_hit', 1.0)
        ))
    elif pnl_pct <= sl['moderate']:
        signals.append(Signal(
            name="stop_loss_near",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason=f"Near stop loss: {pnl_pct*100:.1f}%",
            value=pnl_pct,
            threshold=sl['moderate'],
            weight=weights.get('stop_loss_hit', 1.0) * 0.7
        ))
    
    # Take Profit (MODERATE - check pattern before exiting)
    if pnl_pct >= tp['strong']:
        signals.append(Signal(
            name="take_profit_target",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,  # Not STRONG - let pattern decide
            reason=f"Take profit target: {pnl_pct*100:.1f}% >= {tp['strong']*100:.1f}%",
            value=pnl_pct,
            threshold=tp['strong'],
            weight=weights.get('take_profit', 0.6)
        ))
    
    # Trailing Stop
    if entry_price and high_watermark > entry_price:
        high_pnl_pct = (high_watermark - entry_price) / entry_price
        
        # Only activate after minimum profit
        if high_pnl_pct >= ts['activation_pct']:
            drawdown = high_pnl_pct - pnl_pct
            if drawdown >= ts['drop_pct']:
                signals.append(Signal(
                    name="trailing_stop_hit",
                    signal_type=SignalType.EXIT,
                    strength=SignalStrength.STRONG,
                    reason=f"Trailing stop: {drawdown*100:.1f}% drop from {high_pnl_pct*100:.1f}% high",
                    value=drawdown,
                    threshold=ts['drop_pct'],
                    weight=weights.get('trailing_stop_hit', 0.8)
                ))
    
    return signals

# ============================================================================
# PATTERN DETERIORATION DETECTION
# ============================================================================

def _detect_pattern_deterioration(
    price_history: List[Dict],
    technicals: Dict[str, Any],
    entry_pattern: Optional[Dict],
    context: dict
) -> List[Signal]:
    """Detect pattern breakdown signals."""
    signals = []
    rules = context.get('pattern_exit_rules', {})
    weights = context.get('signal_weights', {}).get('exit_signals', {})
    
    if len(price_history) < 5:
        return signals
    
    # === LOWER HIGH DETECTION ===
    lh_rule = rules.get('lower_high', {})
    if lh_rule.get('enabled', True):
        lower_highs = _count_lower_highs(price_history, lh_rule.get('min_drop_pct', 0.005))
        if lower_highs >= lh_rule.get('consecutive_required', 2):
            signals.append(Signal(
                name="lower_high",
                signal_type=SignalType.EXIT,
                strength=SignalStrength[lh_rule.get('signal_strength', 'MODERATE')],
                reason=f"{lower_highs} consecutive lower highs - momentum weakening",
                value=lower_highs,
                weight=weights.get('lower_high', 0.4)
            ))
    
    # === MACD DIVERGENCE ===
    div_rule = rules.get('macd_divergence', {})
    if div_rule.get('enabled', True):
        divergence = _detect_macd_divergence(price_history, technicals, div_rule.get('lookback_periods', 5))
        if divergence:
            signals.append(Signal(
                name="macd_divergence",
                signal_type=SignalType.EXIT,
                strength=SignalStrength[div_rule.get('signal_strength', 'MODERATE')],
                reason="Bearish divergence: price up but MACD down",
                weight=weights.get('macd_divergence', 0.5)
            ))
    
    # === EMA CROSS DOWN ===
    ema_rule = rules.get('ema_cross_down', {})
    if ema_rule.get('enabled', True):
        ema_fast = technicals.get(f"ema_{ema_rule.get('fast_period', 9)}")
        ema_slow = technicals.get(f"ema_{ema_rule.get('slow_period', 20)}") or technicals.get('sma_20')
        if ema_fast and ema_slow and ema_fast < ema_slow:
            signals.append(Signal(
                name="ema_cross_down",
                signal_type=SignalType.EXIT,
                strength=SignalStrength[ema_rule.get('signal_strength', 'MODERATE')],
                reason=f"EMA{ema_rule.get('fast_period', 9)} crossed below EMA{ema_rule.get('slow_period', 20)}",
                value=ema_fast - ema_slow,
                weight=weights.get('ema_cross_down', 0.4)
            ))
    
    # === PATTERN SUPPORT BREAKDOWN ===
    if entry_pattern:
        bd_rule = rules.get('pattern_breakdown', {})
        if bd_rule.get('enabled', True):
            support = entry_pattern.get('support') or entry_pattern.get('stop_loss')
            if support:
                current_price = price_history[-1].get('close', 0)
                break_pct = (support - current_price) / support if support else 0
                if break_pct >= bd_rule.get('support_break_pct', 0.02):
                    signals.append(Signal(
                        name="pattern_breakdown",
                        signal_type=SignalType.EXIT,
                        strength=SignalStrength.STRONG,
                        reason=f"Pattern support broken: {break_pct*100:.1f}% below support",
                        value=break_pct,
                        threshold=bd_rule.get('support_break_pct', 0.02),
                        weight=weights.get('pattern_breakdown', 0.9)
                    ))
    
    return signals

def _count_lower_highs(price_history: List[Dict], min_drop_pct: float) -> int:
    """Count consecutive lower highs in price data."""
    if len(price_history) < 3:
        return 0
    
    count = 0
    highs = [bar.get('high', 0) for bar in price_history[-5:]]
    
    for i in range(len(highs) - 1, 0, -1):
        if highs[i] < highs[i-1] * (1 - min_drop_pct):
            count += 1
        else:
            break
    
    return count

def _detect_macd_divergence(
    price_history: List[Dict],
    technicals: Dict[str, Any],
    lookback: int
) -> bool:
    """Detect bearish MACD divergence (price up, MACD down)."""
    if len(price_history) < lookback:
        return False
    
    # Get recent price highs
    recent_highs = [bar.get('high', 0) for bar in price_history[-lookback:]]
    
    # Check if price making higher highs
    price_higher_high = recent_highs[-1] > max(recent_highs[:-1])
    
    # Check MACD (simplified - would need MACD history for full detection)
    macd = technicals.get('macd', 0)
    macd_signal = technicals.get('macd_signal', 0)
    
    # Bearish if MACD below signal while price at highs
    macd_bearish = macd < macd_signal
    
    return price_higher_high and macd_bearish

# ============================================================================
# HOLD SIGNAL DETECTION
# ============================================================================

def _analyze_pattern_health(
    price_history: List[Dict],
    technicals: Dict[str, Any],
    context: dict
) -> Dict[str, Any]:
    """Analyze overall pattern health for hold decisions."""
    hold_rules = context.get('hold_conditions', {})
    
    health = {
        'higher_lows': False,
        'above_ema9': False,
        'above_sma20': False,
        'above_vwap': False,
        'volume_confirming': False,
        'macd_expanding': False,
        'rsi_healthy': False,
    }
    
    if len(price_history) < 3:
        return health
    
    # Higher Lows
    hl_rule = hold_rules.get('higher_lows', {})
    if hl_rule.get('enabled', True):
        lows = [bar.get('low', 0) for bar in price_history[-5:]]
        higher_low_count = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i-1] * (1 + hl_rule.get('min_rise_pct', 0.005)))
        health['higher_lows'] = higher_low_count >= hl_rule.get('consecutive_required', 2)
    
    # Above MAs
    current_price = price_history[-1].get('close', 0)
    ema9 = technicals.get('ema_9') or technicals.get('ema9')
    sma20 = technicals.get('sma_20') or technicals.get('sma20')
    vwap = technicals.get('vwap')
    
    if ema9:
        health['above_ema9'] = current_price > ema9
    if sma20:
        health['above_sma20'] = current_price > sma20
    if vwap:
        vwap_rule = hold_rules.get('above_vwap', {})
        min_above = vwap_rule.get('min_above_pct', 0.01)
        health['above_vwap'] = current_price > vwap * (1 + min_above)
    
    # RSI Healthy
    rsi = technicals.get('rsi', 50)
    rsi_rule = hold_rules.get('rsi_healthy', {})
    health['rsi_healthy'] = rsi_rule.get('min_rsi', 45) <= rsi <= rsi_rule.get('max_rsi', 70)
    
    # MACD Expanding
    macd_hist = technicals.get('macd_histogram', 0)
    health['macd_expanding'] = macd_hist > 0
    
    return health

def _pattern_health_to_signals(pattern_health: Dict[str, Any], context: dict) -> List[Signal]:
    """Convert pattern health analysis to hold signals."""
    signals = []
    hold_rules = context.get('hold_conditions', {})
    weights = context.get('signal_weights', {}).get('hold_signals', {})
    
    if pattern_health.get('higher_lows'):
        rule = hold_rules.get('higher_lows', {})
        signals.append(Signal(
            name="higher_lows",
            signal_type=SignalType.HOLD,
            strength=SignalStrength[rule.get('signal_strength', 'STRONG')],
            reason="Higher lows pattern - healthy uptrend",
            weight=weights.get('higher_lows', 0.8)
        ))
    
    if pattern_health.get('above_ema9') and pattern_health.get('above_sma20'):
        rule = hold_rules.get('above_moving_averages', {})
        signals.append(Signal(
            name="above_key_mas",
            signal_type=SignalType.HOLD,
            strength=SignalStrength[rule.get('signal_strength', 'MODERATE')],
            reason="Price above EMA9 and SMA20 - trend intact",
            weight=weights.get('above_moving_averages', 0.6)
        ))
    
    if pattern_health.get('above_vwap'):
        rule = hold_rules.get('above_vwap', {})
        signals.append(Signal(
            name="above_vwap",
            signal_type=SignalType.HOLD,
            strength=SignalStrength[rule.get('signal_strength', 'MODERATE')],
            reason="Trading above VWAP - bullish",
            weight=weights.get('above_vwap', 0.4)
        ))
    
    if pattern_health.get('rsi_healthy'):
        rule = hold_rules.get('rsi_healthy', {})
        signals.append(Signal(
            name="rsi_healthy",
            signal_type=SignalType.HOLD,
            strength=SignalStrength[rule.get('signal_strength', 'WEAK')],
            reason="RSI in healthy zone",
            weight=weights.get('rsi_healthy', 0.3)
        ))
    
    return signals

# ============================================================================
# RECOMMENDATION LOGIC
# ============================================================================

def _determine_recommendation(
    exit_signals: List[Signal],
    hold_signals: List[Signal],
    context: dict
) -> tuple[str, float]:
    """Determine overall recommendation based on signals."""
    
    # STRONG exit = immediate exit
    strong_exits = [s for s in exit_signals if s.strength == SignalStrength.STRONG]
    if strong_exits:
        return "EXIT", 0.95
    
    # Calculate weighted scores
    exit_score = sum(s.weight for s in exit_signals)
    hold_score = sum(s.weight for s in hold_signals)
    
    # No signals = HOLD (maintain position)
    if not exit_signals and not hold_signals:
        return "HOLD", 0.5
    
    # Only hold signals = HOLD with confidence
    if not exit_signals and hold_signals:
        return "HOLD", min(0.9, 0.5 + hold_score * 0.1)
    
    # Only exit signals (MODERATE) = CONSULT_AI
    if exit_signals and not hold_signals:
        moderate_exits = [s for s in exit_signals if s.strength == SignalStrength.MODERATE]
        if moderate_exits:
            return "CONSULT_AI", 0.6
        return "HOLD", 0.5  # Only WEAK exits
    
    # Conflicting signals = CONSULT_AI
    if exit_score > hold_score * 0.8:  # Exit signals winning
        return "CONSULT_AI", 0.5 + (exit_score - hold_score) * 0.1
    else:  # Hold signals winning
        return "HOLD", 0.5 + (hold_score - exit_score) * 0.1

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_thresholds(context: dict, market: str) -> dict:
    """Get thresholds with market-specific overrides applied."""
    base = context.get('thresholds', {}).copy()
    
    overrides = context.get('market_overrides', {}).get(market, {}).get('thresholds', {})
    
    # Deep merge overrides
    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = {**base[key], **value}
        else:
            base[key] = value
    
    return base

def _detect_technical_exit_signals(technicals: Dict[str, Any], context: dict) -> List[Signal]:
    """Detect technical indicator exit signals."""
    signals = []
    tech_thresholds = context.get('technical', {})
    weights = context.get('signal_weights', {}).get('exit_signals', {})
    
    # RSI Overbought
    rsi = technicals.get('rsi')
    if rsi:
        rsi_th = tech_thresholds.get('rsi', {})
        if rsi >= rsi_th.get('overbought_strong', 85):
            signals.append(Signal(
                name="rsi_overbought",
                signal_type=SignalType.EXIT,
                strength=SignalStrength.STRONG,
                reason=f"RSI overbought: {rsi:.0f} >= {rsi_th.get('overbought_strong', 85)}",
                value=rsi,
                threshold=rsi_th.get('overbought_strong', 85),
                weight=weights.get('rsi_overbought', 0.7)
            ))
        elif rsi >= rsi_th.get('overbought_moderate', 75):
            signals.append(Signal(
                name="rsi_elevated",
                signal_type=SignalType.EXIT,
                strength=SignalStrength.MODERATE,
                reason=f"RSI elevated: {rsi:.0f}",
                value=rsi,
                threshold=rsi_th.get('overbought_moderate', 75),
                weight=weights.get('rsi_overbought', 0.7) * 0.7
            ))
    
    return signals

def _detect_technical_hold_signals(technicals: Dict[str, Any], current_price: float, context: dict) -> List[Signal]:
    """Detect technical indicator hold signals."""
    # Implemented via pattern_health_to_signals
    return []

def _detect_volume_exit_signals(current_volume: float, entry_volume: float, context: dict) -> List[Signal]:
    """Detect volume-based exit signals."""
    signals = []
    vol_th = context.get('technical', {}).get('volume', {})
    weights = context.get('signal_weights', {}).get('exit_signals', {})
    
    ratio = current_volume / entry_volume if entry_volume > 0 else 1.0
    
    if ratio <= vol_th.get('collapse_strong', 0.25):
        signals.append(Signal(
            name="volume_collapse",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            reason=f"Volume collapsed: {ratio*100:.0f}% of entry",
            value=ratio,
            threshold=vol_th.get('collapse_strong', 0.25),
            weight=weights.get('volume_collapse', 0.6)
        ))
    elif ratio <= vol_th.get('collapse_moderate', 0.40):
        signals.append(Signal(
            name="volume_weak",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason=f"Volume weak: {ratio*100:.0f}% of entry",
            value=ratio,
            threshold=vol_th.get('collapse_moderate', 0.40),
            weight=weights.get('volume_collapse', 0.6) * 0.7
        ))
    
    return signals

def _detect_volume_hold_signals(current_volume: float, entry_volume: float, context: dict) -> List[Signal]:
    """Detect volume-based hold signals."""
    signals = []
    vol_th = context.get('technical', {}).get('volume', {})
    weights = context.get('signal_weights', {}).get('hold_signals', {})
    
    ratio = current_volume / entry_volume if entry_volume > 0 else 1.0
    
    if ratio >= vol_th.get('strong_min', 1.20):
        signals.append(Signal(
            name="volume_strong",
            signal_type=SignalType.HOLD,
            strength=SignalStrength.STRONG,
            reason=f"Strong volume: {ratio*100:.0f}% of entry",
            value=ratio,
            weight=weights.get('volume_confirmation', 0.6)
        ))
    elif ratio >= vol_th.get('healthy_min', 0.80):
        signals.append(Signal(
            name="volume_healthy",
            signal_type=SignalType.HOLD,
            strength=SignalStrength.MODERATE,
            reason=f"Healthy volume: {ratio*100:.0f}% of entry",
            value=ratio,
            weight=weights.get('volume_confirmation', 0.6) * 0.7
        ))
    
    return signals

def _detect_time_signals(entry_time: datetime, pnl_pct: float, context: dict, market: str) -> List[Signal]:
    """Detect time-based exit signals."""
    signals = []
    time_th = context.get('thresholds', {}).get('time_stop', {})
    
    # Time stop for flat positions
    if entry_time:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
        
        minutes_held = (now - entry_time).total_seconds() / 60
        
        # Flat position too long
        if abs(pnl_pct) < 0.01 and minutes_held >= time_th.get('minutes_flat', 120):
            signals.append(Signal(
                name="time_stop_flat",
                signal_type=SignalType.EXIT,
                strength=SignalStrength.MODERATE,
                reason=f"Position flat for {minutes_held:.0f} minutes",
                value=minutes_held,
                threshold=time_th.get('minutes_flat', 120)
            ))
    
    return signals
```

---

## 6. Pattern Deterioration Rules

### Summary of Pattern Exit Signals

| Signal | Detection Logic | Strength | When to Exit |
|--------|-----------------|----------|--------------|
| **Lower High** | 2+ consecutive highs lower than previous | MODERATE | Momentum weakening |
| **Pattern Breakdown** | Price 2%+ below entry pattern support | STRONG | Entry thesis invalid |
| **MACD Divergence** | Price higher high, MACD lower high | MODERATE | Hidden weakness |
| **EMA Cross Down** | 9 EMA crosses below 20 EMA | MODERATE | Trend reversal |
| **Failed Retest** | Breakout retest fails, drops 2% | STRONG | Breakout rejected |
| **Consolidation Stall** | <2% range for 10+ periods | WEAK | Momentum dead |

### Detection Priority

```
1. Pattern Breakdown (STRONG)     ← Exit immediately if pattern broken
2. Failed Retest (STRONG)         ← Exit immediately if breakout fails
3. Lower High (MODERATE)          ← Consult AI
4. MACD Divergence (MODERATE)     ← Consult AI  
5. EMA Cross Down (MODERATE)      ← Consult AI
6. Consolidation Stall (WEAK)     ← Monitor only
```

---

## 7. Hold Conditions

### Summary of Hold Signals

| Signal | Detection Logic | Strength | Let Position Run |
|--------|-----------------|----------|------------------|
| **Higher Lows** | 2+ consecutive lows higher than previous | STRONG | Accumulation phase |
| **Above Key MAs** | Price > 9 EMA AND Price > 20 SMA | MODERATE | Trend intact |
| **Volume Confirmation** | Up candle volume > down candle volume | MODERATE | Buying pressure |
| **MACD Expansion** | Histogram growing for 3+ periods | MODERATE | Momentum accelerating |
| **Above VWAP** | Price 1%+ above VWAP | MODERATE | Bullish positioning |
| **RSI Healthy** | RSI between 45-70 | WEAK | Room to run |

### Hold Priority

```
HOLD when:
├── Higher Lows (STRONG)          ← Strongest hold signal
├── Above Key MAs (MODERATE)      ← Trend confirmation
├── Volume Confirmation           ← Buying pressure present
└── RSI Healthy                   ← Not overextended
```

---

## 8. Implementation Plan

### Phase Overview

```
Week 1:     PHASE 1 - FOUNDATION
            ├── Create exit_context.yaml
            ├── Update signals.py with context loader
            └── Unit tests for new functions

Week 2:     PHASE 2 - INTEGRATION  
            ├── Update position_monitor_service.py
            ├── Add price_history to monitoring loop
            └── Integration tests

Week 3:     PHASE 3 - DEPLOYMENT
            ├── Deploy to intl_claude (paper first)
            ├── Monitor and tune thresholds
            └── Deploy to dev_claude

Week 4:     PHASE 4 - OPTIMIZATION
            ├── Analyze results
            ├── Tune context based on performance
            └── Document learnings
```

### Detailed Task List

| Priority | Task | Files | Effort | Dependencies |
|----------|------|-------|--------|--------------|
| **1** | Create `config/exit_context.yaml` | New file | 1 hour | None |
| **2** | Update `signals.py` with context loader | signals.py | 2 hours | Task 1 |
| **3** | Add pattern deterioration detection | signals.py | 3 hours | Task 2 |
| **4** | Add hold signal detection | signals.py | 2 hours | Task 2 |
| **5** | Update `position_monitor_service.py` to pass price_history | position_monitor_service.py | 2 hours | Tasks 2-4 |
| **6** | Add entry pattern tracking to positions table | SQL migration | 1 hour | None |
| **7** | Unit tests for new signals | test_signals.py | 2 hours | Tasks 2-4 |
| **8** | Integration tests | test_integration.py | 2 hours | Tasks 5-6 |
| **9** | Deploy to intl_claude (paper) | Deployment | 1 hour | All above |
| **10** | Monitor and tune | Ongoing | 1 week | Task 9 |
| **11** | Deploy to dev_claude | Deployment | 1 hour | Task 10 |

**Total Estimated Effort:** ~16 hours + 1 week monitoring

---

## 9. File Specifications

### Files to Create

| File | Location | Purpose | Lines |
|------|----------|---------|-------|
| `exit_context.yaml` | `config/` | Exit strategy configuration | ~300 |

### Files to Update

| File | Changes | Impact |
|------|---------|--------|
| `signals.py` | Add context loader, pattern detection, hold signals | Major |
| `position_monitor_service.py` | Pass price_history, use new analyze_position() | Medium |
| Database | Add `entry_pattern` column to positions | Minor |

### File Structure After Implementation

```
catalyst-international/
├── config/
│   ├── intl_claude_config.yaml    # Existing agent config
│   ├── news_context.yaml          # News detection context
│   └── exit_context.yaml          # EXIT CONTEXT (NEW)
├── data/
│   ├── signals.py                 # UPDATED with context-separated architecture
│   ├── patterns.py                # Existing pattern detection
│   └── market.py                  # Existing market data
├── position_monitor_service.py    # UPDATED to use new signals
└── unified_agent.py               # No changes needed

catalyst-dev/
├── config/
│   └── exit_context.yaml          # Same format, US-specific values
├── signals.py                     # UPDATED
└── position_monitor_service.py    # UPDATED
```

---

## 10. Testing Strategy

### Unit Tests

```python
# test_signals.py

def test_context_loading():
    """Test that context loads and hot-reloads."""
    context = load_exit_context()
    assert context['version'] == '1.0.0'
    assert 'thresholds' in context

def test_stop_loss_detection():
    """Test stop loss signal detection."""
    position = {'pnl_pct': -0.035, 'entry_price': 100, 'current_price': 96.5}
    quote = {'price': 96.5, 'volume': 10000}
    technicals = {'rsi': 50}
    
    analysis = analyze_position(position, quote, technicals, market='hkex')
    
    assert analysis.immediate_exit == True
    assert any(s.name == 'stop_loss_hit' for s in analysis.exit_signals)

def test_pattern_deterioration():
    """Test lower high detection."""
    price_history = [
        {'high': 100, 'low': 98, 'close': 99},
        {'high': 99, 'low': 97, 'close': 98},   # Lower high
        {'high': 98, 'low': 96, 'close': 97},   # Lower high
    ]
    
    analysis = analyze_position(
        position={'pnl_pct': 0.01, 'entry_price': 95},
        quote={'price': 97, 'volume': 10000},
        technicals={'rsi': 55},
        price_history=price_history,
        market='hkex'
    )
    
    assert any(s.name == 'lower_high' for s in analysis.exit_signals)

def test_hold_signals():
    """Test higher lows hold detection."""
    price_history = [
        {'high': 100, 'low': 95, 'close': 99},
        {'high': 102, 'low': 96, 'close': 101},  # Higher low
        {'high': 104, 'low': 97, 'close': 103},  # Higher low
    ]
    
    analysis = analyze_position(
        position={'pnl_pct': 0.05, 'entry_price': 95},
        quote={'price': 103, 'volume': 15000},
        technicals={'rsi': 60, 'ema_9': 100, 'sma_20': 98},
        price_history=price_history,
        market='hkex'
    )
    
    assert any(s.name == 'higher_lows' for s in analysis.hold_signals)
    assert analysis.recommendation == 'HOLD'
```

### Integration Tests

```python
# test_integration.py

def test_position_monitor_with_new_signals():
    """Test position monitor uses new signal analysis."""
    # Create test position
    # Run monitoring cycle
    # Verify signals detected correctly
    pass

def test_context_hot_reload():
    """Test that context changes are picked up."""
    # Modify exit_context.yaml
    # Call reload_context()
    # Verify new values used
    pass
```

---

## 11. Rollback Plan

### If Issues Arise

1. **Revert signals.py** to previous version (v2.0.0)
2. **Remove exit_context.yaml** (or rename to .bak)
3. **Restart position_monitor_service**

### Rollback Commands

```bash
# On intl_claude droplet
cd /root/catalyst-international

# Backup current files
cp data/signals.py data/signals.py.v3
cp config/exit_context.yaml config/exit_context.yaml.bak

# Restore previous version
git checkout HEAD~1 -- data/signals.py

# Restart service
sudo systemctl restart position-monitor-intl
```

### Feature Flags

The context file includes enable/disable flags for each rule:

```yaml
pattern_exit_rules:
  lower_high:
    enabled: true   # ← Set to false to disable
```

This allows disabling individual rules without code changes.

---

## Summary

### What We're Building

| Component | Before | After |
|-----------|--------|-------|
| **Configuration** | Hardcoded in Python | YAML file (exit_context.yaml) |
| **Exit Signals** | P&L thresholds only | P&L + Pattern + Technical |
| **Hold Signals** | None | Higher lows, trend intact, volume |
| **Tuning** | Edit code → redeploy | Edit YAML → auto-reload |
| **Market Support** | Same for all | Market-specific overrides |

### Expected Impact

| Metric | Current | Expected |
|--------|---------|----------|
| Avg losing trade | -3.0% | -1.5% |
| Avg winning trade | +5.0% | +7.0% |
| False exits (good trades cut early) | ~40% | ~15% |
| Config iteration time | Hours | Minutes |

---

**Ready for implementation.** 

Start with Task 1: Create `config/exit_context.yaml` on the droplet.

---

*Design Document v1.0.0 | Context-Separated Exit Strategy | 2026-01-24*
