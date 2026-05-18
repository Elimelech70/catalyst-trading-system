#!/usr/bin/env python3
"""
Comprehensive Test Suite for signals.py v3.0.0
Tests all exit signals, hold signals, pattern detection, and edge cases.
"""

import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from signals import (
    load_exit_context,
    reload_context,
    _get_thresholds,
    detect_pnl_signals,
    detect_rsi_signals,
    detect_volume_signals,
    detect_trend_signals,
    detect_pattern_deterioration,
    detect_time_signals,
    analyze_pattern_health,
    pattern_health_to_signals,
    analyze_position,
    SignalStrength,
    SignalType,
)

HK_TZ = ZoneInfo("Asia/Hong_Kong")

# Test counters
tests_passed = 0
tests_failed = 0
test_results = []


def test(name, condition, details=""):
    """Record test result."""
    global tests_passed, tests_failed
    if condition:
        tests_passed += 1
        status = "✓ PASS"
    else:
        tests_failed += 1
        status = "✗ FAIL"
    result = f"{status}: {name}"
    if details and not condition:
        result += f" - {details}"
    test_results.append(result)
    print(result)


def run_all_tests():
    """Run all test suites."""
    print("=" * 70)
    print("COMPREHENSIVE SIGNAL DETECTION TEST SUITE")
    print("signals.py v3.0.0 - Context-Separated Architecture")
    print("=" * 70)

    test_context_loading()
    test_pnl_signals()
    test_rsi_signals()
    test_volume_signals()
    test_trend_signals()
    test_pattern_deterioration()
    test_hold_signals()
    test_market_overrides()
    test_time_signals()
    test_recommendation_logic()
    test_edge_cases()

    print("\n" + "=" * 70)
    print(f"RESULTS: {tests_passed} passed, {tests_failed} failed")
    print("=" * 70)

    if tests_failed > 0:
        print("\nFailed tests:")
        for r in test_results:
            if "FAIL" in r:
                print(f"  {r}")

    return tests_failed == 0


def test_context_loading():
    """Test 1: Context Loading and Hot-Reload"""
    print("\n--- Test Suite 1: Context Loading ---")

    # Test basic loading
    ctx = load_exit_context()
    test("Context loads successfully", ctx is not None)
    test("Context has version", ctx.get("version") == "1.0.0", f"got {ctx.get('version')}")
    test("Context has thresholds", "thresholds" in ctx)
    test("Context has pattern_exit_rules", "pattern_exit_rules" in ctx)
    test("Context has hold_conditions", "hold_conditions" in ctx)
    test("Context has signal_weights", "signal_weights" in ctx)

    # Test specific values
    sl = ctx.get("thresholds", {}).get("stop_loss", {})
    test("Stop loss strong is -0.03", sl.get("strong") == -0.03, f"got {sl.get('strong')}")
    test("Stop loss moderate is -0.02", sl.get("moderate") == -0.02)

    # Test reload
    ctx2 = reload_context()
    test("Reload returns context", ctx2 is not None)
    test("Reload returns same version", ctx2.get("version") == ctx.get("version"))


def test_pnl_signals():
    """Test 2: P&L-based Exit Signals"""
    print("\n--- Test Suite 2: P&L Exit Signals ---")

    ctx = load_exit_context()

    # Test stop loss strong
    signals = detect_pnl_signals(-0.035, 0, 100, ctx, "hkex")
    stop_loss = [s for s in signals if s.name == "stop_loss_hit"]
    test("Stop loss STRONG at -3.5%", len(stop_loss) == 1 and stop_loss[0].strength == SignalStrength.STRONG)

    # Test stop loss moderate
    signals = detect_pnl_signals(-0.025, 0, 100, ctx, "hkex")
    stop_near = [s for s in signals if s.name == "stop_loss_near"]
    test("Stop loss MODERATE at -2.5%", len(stop_near) == 1 and stop_near[0].strength == SignalStrength.MODERATE)

    # Test no stop loss at -1%
    signals = detect_pnl_signals(-0.01, 0, 100, ctx, "hkex")
    stop_any = [s for s in signals if "stop_loss" in s.name]
    test("No stop loss at -1%", len(stop_any) == 0)

    # Test trailing stop - activated
    signals = detect_pnl_signals(0.04, 0.08, 100, ctx, "hkex")  # 4% drawdown from 8% high
    trailing = [s for s in signals if s.name == "trailing_stop_hit"]
    test("Trailing stop STRONG (4% drop from 8% high)",
         len(trailing) == 1 and trailing[0].strength == SignalStrength.STRONG,
         f"got {len(trailing)} signals")

    # Test trailing stop - not activated (high not enough)
    signals = detect_pnl_signals(0.02, 0.025, 100, ctx, "hkex")  # Only 0.5% drawdown from 2.5% high
    trailing = [s for s in signals if s.name == "trailing_stop_hit"]
    test("No trailing stop (high watermark too low)", len(trailing) == 0)

    # Test take profit target
    signals = detect_pnl_signals(0.12, 0.12, 100, ctx, "hkex")  # 12% profit
    tp = [s for s in signals if s.name == "take_profit_target"]
    test("Take profit MODERATE at +12%", len(tp) == 1 and tp[0].strength == SignalStrength.MODERATE)

    # Test healthy profit hold signal
    signals = detect_pnl_signals(0.04, 0.04, 100, ctx, "hkex")
    healthy = [s for s in signals if s.name == "healthy_profit"]
    test("Healthy profit HOLD at +4%", len(healthy) == 1 and healthy[0].signal_type == SignalType.HOLD)


def test_rsi_signals():
    """Test 3: RSI-based Signals"""
    print("\n--- Test Suite 3: RSI Signals ---")

    ctx = load_exit_context()

    # Test overbought strong
    signals = detect_rsi_signals(88, ctx)
    ob = [s for s in signals if s.name == "rsi_overbought"]
    test("RSI overbought STRONG at 88", len(ob) == 1 and ob[0].strength == SignalStrength.STRONG)

    # Test overbought moderate
    signals = detect_rsi_signals(78, ctx)
    elevated = [s for s in signals if s.name == "rsi_elevated"]
    test("RSI elevated MODERATE at 78", len(elevated) == 1 and elevated[0].strength == SignalStrength.MODERATE)

    # Test healthy RSI hold
    signals = detect_rsi_signals(55, ctx)
    healthy = [s for s in signals if s.name == "rsi_healthy"]
    test("RSI healthy HOLD at 55", len(healthy) == 1 and healthy[0].signal_type == SignalType.HOLD)

    # Test RSI at boundary (45)
    signals = detect_rsi_signals(45, ctx)
    healthy = [s for s in signals if s.name == "rsi_healthy"]
    test("RSI healthy at boundary 45", len(healthy) == 1)

    # Test RSI at boundary (70)
    signals = detect_rsi_signals(70, ctx)
    healthy = [s for s in signals if s.name == "rsi_healthy"]
    test("RSI healthy at boundary 70", len(healthy) == 1)

    # Test RSI outside healthy range (high side)
    signals = detect_rsi_signals(72, ctx)
    healthy = [s for s in signals if s.name == "rsi_healthy"]
    test("No RSI healthy at 72", len(healthy) == 0)

    # Test None RSI
    signals = detect_rsi_signals(None, ctx)
    test("No signals for None RSI", len(signals) == 0)


def test_volume_signals():
    """Test 4: Volume-based Signals"""
    print("\n--- Test Suite 4: Volume Signals ---")

    ctx = load_exit_context()

    # Test volume collapse strong (<25%)
    signals = detect_volume_signals(20000, 100000, ctx)
    collapse = [s for s in signals if s.name == "volume_collapse"]
    test("Volume collapse STRONG at 20%", len(collapse) == 1 and collapse[0].strength == SignalStrength.STRONG)

    # Test volume weak moderate (<40%)
    signals = detect_volume_signals(35000, 100000, ctx)
    weak = [s for s in signals if s.name == "volume_weak"]
    test("Volume weak MODERATE at 35%", len(weak) == 1 and weak[0].strength == SignalStrength.MODERATE)

    # Test volume strong (>120%)
    signals = detect_volume_signals(150000, 100000, ctx)
    strong = [s for s in signals if s.name == "volume_strong"]
    test("Volume strong HOLD at 150%", len(strong) == 1 and strong[0].signal_type == SignalType.HOLD)

    # Test volume healthy (80-120%)
    signals = detect_volume_signals(90000, 100000, ctx)
    healthy = [s for s in signals if s.name == "volume_healthy"]
    test("Volume healthy HOLD at 90%", len(healthy) == 1)

    # Test no entry volume
    signals = detect_volume_signals(50000, 0, ctx)
    test("No signals when entry volume is 0", len(signals) == 0)

    # Test no signals in middle range (40-80%)
    signals = detect_volume_signals(60000, 100000, ctx)
    test("No signals at 60% volume", len(signals) == 0)


def test_trend_signals():
    """Test 5: Trend-based Signals (VWAP, EMA, MACD)"""
    print("\n--- Test Suite 5: Trend Signals ---")

    ctx = load_exit_context()

    # Test above VWAP
    technicals = {"vwap": 100, "ema_9": 101, "sma_20": 100}
    signals = detect_trend_signals(103, technicals, ctx)  # 3% above VWAP
    above_vwap = [s for s in signals if s.name == "above_vwap"]
    test("Above VWAP HOLD at +3%", len(above_vwap) == 1 and above_vwap[0].signal_type == SignalType.HOLD)

    # Test below VWAP
    signals = detect_trend_signals(97, technicals, ctx)  # 3% below VWAP
    below_vwap = [s for s in signals if s.name == "below_vwap"]
    test("Below VWAP EXIT at -3%", len(below_vwap) == 1 and below_vwap[0].signal_type == SignalType.EXIT)

    # Test above key MAs
    technicals = {"vwap": 100, "ema_9": 98, "sma_20": 97}
    signals = detect_trend_signals(100, technicals, ctx)
    above_mas = [s for s in signals if s.name == "above_key_mas"]
    test("Above key MAs HOLD", len(above_mas) == 1)

    # Test not above both MAs
    technicals = {"vwap": 100, "ema_9": 101, "sma_20": 99}
    signals = detect_trend_signals(100, technicals, ctx)
    above_mas = [s for s in signals if s.name == "above_key_mas"]
    test("Not above both MAs (EMA9 > price)", len(above_mas) == 0)

    # Test MACD bearish
    technicals = {"macd": 0.3, "macd_signal": 0.5, "macd_histogram": -0.2}
    signals = detect_trend_signals(100, technicals, ctx)
    macd_bear = [s for s in signals if s.name == "macd_bearish"]
    test("MACD bearish EXIT", len(macd_bear) == 1 and macd_bear[0].signal_type == SignalType.EXIT)

    # Test MACD bullish
    technicals = {"macd": 0.5, "macd_signal": 0.3, "macd_histogram": 0.2}
    signals = detect_trend_signals(100, technicals, ctx)
    macd_bull = [s for s in signals if s.name == "macd_bullish"]
    test("MACD bullish HOLD", len(macd_bull) == 1 and macd_bull[0].signal_type == SignalType.HOLD)


def test_pattern_deterioration():
    """Test 6: Pattern Deterioration Detection"""
    print("\n--- Test Suite 6: Pattern Deterioration ---")

    ctx = load_exit_context()

    # Test lower highs detection
    price_history = [
        {"high": 105, "low": 100, "close": 103},
        {"high": 104, "low": 99, "close": 102},
        {"high": 103, "low": 98, "close": 101},
        {"high": 102, "low": 97, "close": 100},
        {"high": 101, "low": 96, "close": 99},
    ]
    technicals = {"rsi": 50}
    signals = detect_pattern_deterioration(price_history, technicals, None, ctx)
    lower_high = [s for s in signals if s.name == "lower_high"]
    test("Lower highs detected (4 consecutive)", len(lower_high) == 1, f"got {len(lower_high)}")

    # Test no lower highs (uptrend)
    price_history = [
        {"high": 100, "low": 95, "close": 98},
        {"high": 102, "low": 97, "close": 100},
        {"high": 104, "low": 99, "close": 102},
        {"high": 106, "low": 101, "close": 104},
        {"high": 108, "low": 103, "close": 106},
    ]
    signals = detect_pattern_deterioration(price_history, technicals, None, ctx)
    lower_high = [s for s in signals if s.name == "lower_high"]
    test("No lower highs in uptrend", len(lower_high) == 0)

    # Test MACD divergence
    price_history = [
        {"high": 100, "low": 95, "close": 98},
        {"high": 102, "low": 97, "close": 100},
        {"high": 104, "low": 99, "close": 102},
        {"high": 103, "low": 98, "close": 101},
        {"high": 105, "low": 100, "close": 104},  # Higher high
    ]
    technicals = {"macd": 0.3, "macd_signal": 0.5}  # But MACD below signal
    signals = detect_pattern_deterioration(price_history, technicals, None, ctx)
    divergence = [s for s in signals if s.name == "macd_divergence"]
    test("MACD divergence detected", len(divergence) == 1)

    # Test EMA cross down
    technicals = {"ema_9": 98, "sma_20": 100}  # EMA below SMA
    signals = detect_pattern_deterioration(price_history, technicals, None, ctx)
    ema_cross = [s for s in signals if s.name == "ema_cross_down"]
    test("EMA cross down detected", len(ema_cross) == 1)

    # Test pattern breakdown
    entry_pattern = {"support": 100}
    price_history[-1] = {"high": 98, "low": 95, "close": 97}  # 3% below support
    signals = detect_pattern_deterioration(price_history, technicals, entry_pattern, ctx)
    breakdown = [s for s in signals if s.name == "pattern_breakdown"]
    test("Pattern breakdown STRONG", len(breakdown) == 1 and breakdown[0].strength == SignalStrength.STRONG)

    # Test consolidation stall (need 10+ bars)
    price_history = [{"high": 100.5, "low": 99.5, "close": 100} for _ in range(12)]
    technicals = {"ema_9": 100, "sma_20": 100}
    signals = detect_pattern_deterioration(price_history, technicals, None, ctx)
    stall = [s for s in signals if s.name == "consolidation_stall"]
    test("Consolidation stall detected", len(stall) == 1)

    # Test insufficient history
    signals = detect_pattern_deterioration([{"high": 100}], technicals, None, ctx)
    test("No signals with insufficient history", len(signals) == 0)


def test_hold_signals():
    """Test 7: Hold Signal Detection (Pattern Health)"""
    print("\n--- Test Suite 7: Hold Signals ---")

    ctx = load_exit_context()

    # Test higher lows detection
    price_history = [
        {"high": 100, "low": 95, "close": 98},
        {"high": 102, "low": 96, "close": 100},
        {"high": 104, "low": 97, "close": 102},
        {"high": 106, "low": 98, "close": 104},
        {"high": 108, "low": 99, "close": 106},
    ]
    technicals = {"rsi": 55, "ema_9": 104, "sma_20": 102, "macd_histogram": 0.5}

    health = analyze_pattern_health(price_history, technicals, ctx)
    test("Higher lows detected", health["higher_lows"] == True)
    test("Higher lows count >= 2", health["higher_lows_count"] >= 2)
    test("Above EMA9 detected", health["above_ema9"] == True)
    test("Above SMA20 detected", health["above_sma20"] == True)
    test("MACD expanding detected", health["macd_expanding"] == True)
    test("RSI healthy detected", health["rsi_healthy"] == True)

    # Convert to signals
    signals = pattern_health_to_signals(health, ctx)
    higher_lows_sig = [s for s in signals if s.name == "higher_lows"]
    test("Higher lows signal STRONG", len(higher_lows_sig) == 1 and higher_lows_sig[0].strength == SignalStrength.STRONG)

    above_mas_sig = [s for s in signals if s.name == "above_key_mas"]
    test("Above key MAs signal", len(above_mas_sig) == 1)

    # Test no higher lows (flat)
    price_history = [
        {"high": 100, "low": 95, "close": 98},
        {"high": 100, "low": 95, "close": 98},
        {"high": 100, "low": 95, "close": 98},
        {"high": 100, "low": 95, "close": 98},
        {"high": 100, "low": 95, "close": 98},
    ]
    health = analyze_pattern_health(price_history, technicals, ctx)
    test("No higher lows in flat pattern", health["higher_lows"] == False)


def test_market_overrides():
    """Test 8: Market-Specific Threshold Overrides"""
    print("\n--- Test Suite 8: Market Overrides ---")

    ctx = load_exit_context()

    # Test HKEX overrides
    hkex_th = _get_thresholds(ctx, "hkex")
    test("HKEX stop loss is -3.5%", hkex_th["stop_loss"]["strong"] == -0.035)
    test("HKEX take profit is +12%", hkex_th["take_profit"]["strong"] == 0.12)
    test("HKEX trailing stop is 3%", hkex_th["trailing_stop"]["drop_pct"] == 0.03)

    # Test US overrides
    us_th = _get_thresholds(ctx, "us")
    test("US stop loss is -5%", us_th["stop_loss"]["strong"] == -0.05)
    test("US take profit is +10%", us_th["take_profit"]["strong"] == 0.10)
    test("US trailing stop activation is 4%", us_th["trailing_stop"]["activation_pct"] == 0.04)

    # Test signal detection with different markets
    signals_hkex = detect_pnl_signals(-0.04, 0, 100, ctx, "hkex")
    signals_us = detect_pnl_signals(-0.04, 0, 100, ctx, "us")

    hkex_stop = [s for s in signals_hkex if s.name == "stop_loss_hit"]
    us_stop = [s for s in signals_us if s.name == "stop_loss_hit"]

    test("HKEX triggers stop at -4%", len(hkex_stop) == 1)
    test("US does NOT trigger stop at -4%", len(us_stop) == 0)  # US threshold is -5%

    # Test US triggers at -5%
    signals_us = detect_pnl_signals(-0.05, 0, 100, ctx, "us")
    us_stop = [s for s in signals_us if s.name == "stop_loss_hit"]
    test("US triggers stop at -5%", len(us_stop) == 1)


def test_time_signals():
    """Test 9: Time-based Signals"""
    print("\n--- Test Suite 9: Time Signals ---")

    ctx = load_exit_context()

    # We can't easily test market close signals without mocking time
    # But we can test the time stop for flat positions

    # Test flat position time stop
    entry_time = datetime.now(HK_TZ) - timedelta(minutes=150)  # 2.5 hours ago
    signals = detect_time_signals(entry_time, 0.005, ctx, "hkex")  # 0.5% P&L (flat)
    time_stop = [s for s in signals if s.name == "time_stop_flat"]
    test("Time stop for flat position (2.5 hours)", len(time_stop) == 1)

    # Test no time stop with movement
    signals = detect_time_signals(entry_time, 0.03, ctx, "hkex")  # 3% P&L
    time_stop = [s for s in signals if s.name == "time_stop_flat"]
    test("No time stop with 3% movement", len(time_stop) == 0)

    # Test no time stop if position is recent
    entry_time = datetime.now(HK_TZ) - timedelta(minutes=60)  # 1 hour ago
    signals = detect_time_signals(entry_time, 0.005, ctx, "hkex")
    time_stop = [s for s in signals if s.name == "time_stop_flat"]
    test("No time stop for recent position (1 hour)", len(time_stop) == 0)

    # Test with string entry time
    entry_time_str = (datetime.now(HK_TZ) - timedelta(minutes=150)).isoformat()
    signals = detect_time_signals(entry_time_str, 0.005, ctx, "hkex")
    time_stop = [s for s in signals if s.name == "time_stop_flat"]
    test("Time stop works with string entry time", len(time_stop) == 1)


def test_recommendation_logic():
    """Test 10: Recommendation Logic"""
    print("\n--- Test Suite 10: Recommendation Logic ---")

    # Test STRONG exit = EXIT
    position = {"pnl_pct": -0.04, "entry_price": 100}
    quote = {"price": 96, "volume": 100000}
    technicals = {"rsi": 50}

    analysis = analyze_position(position, quote, technicals, market="hkex")
    test("STRONG exit signal -> EXIT", analysis.recommendation == "EXIT")
    test("immediate_exit is True", analysis.immediate_exit == True)

    # Test all hold signals = HOLD
    position = {"pnl_pct": 0.03, "entry_price": 100}
    quote = {"price": 103, "volume": 120000}
    technicals = {"rsi": 55, "ema_9": 101, "sma_20": 100, "vwap": 101, "macd": 0.5, "macd_signal": 0.3}
    price_history = [
        {"high": 100, "low": 95, "close": 98},
        {"high": 102, "low": 96, "close": 100},
        {"high": 104, "low": 97, "close": 102},
        {"high": 104, "low": 98, "close": 103},
        {"high": 104, "low": 99, "close": 103},
    ]

    analysis = analyze_position(position, quote, technicals, price_history=price_history,
                               entry_volume=100000, market="hkex")
    test("All hold signals -> HOLD", analysis.recommendation == "HOLD")
    test("immediate_exit is False", analysis.immediate_exit == False)
    test("Has multiple hold signals", len(analysis.hold_signals) >= 3)

    # Test MODERATE exit with STRONG hold = CONSULT_AI
    position = {"pnl_pct": 0.03, "entry_price": 100}
    quote = {"price": 103, "volume": 150000}
    technicals = {"rsi": 78, "ema_9": 101, "sma_20": 100}  # RSI elevated (MODERATE exit)

    analysis = analyze_position(position, quote, technicals, price_history=price_history,
                               entry_volume=100000, market="hkex")
    has_moderate_exit = any(s.strength == SignalStrength.MODERATE for s in analysis.exit_signals)
    has_strong_hold = any(s.strength == SignalStrength.STRONG for s in analysis.hold_signals)
    test("Mixed signals -> CONSULT_AI", analysis.recommendation == "CONSULT_AI")
    test("Has MODERATE exit", has_moderate_exit)
    test("Has STRONG hold", has_strong_hold)

    # Test confidence scores
    position = {"pnl_pct": -0.04, "entry_price": 100}
    analysis = analyze_position(position, {"price": 96, "volume": 100000}, {"rsi": 50}, market="hkex")
    test("EXIT confidence >= 90%", analysis.confidence >= 0.90)


def test_edge_cases():
    """Test 11: Edge Cases and Error Handling"""
    print("\n--- Test Suite 11: Edge Cases ---")

    ctx = load_exit_context()

    # Test with None/empty values
    signals = detect_pnl_signals(0, 0, 0, ctx, "hkex")
    test("No crash with zero P&L", True)

    signals = detect_volume_signals(0, 0, ctx)
    test("No crash with zero volumes", len(signals) == 0)

    signals = detect_rsi_signals(None, ctx)
    test("No crash with None RSI", len(signals) == 0)

    # Test analyze_position with minimal data
    analysis = analyze_position(
        position={"pnl_pct": 0},
        quote={"price": 100},
        technicals={},
        market="hkex"
    )
    test("analyze_position works with minimal data", analysis is not None)
    test("Recommendation is valid", analysis.recommendation in ["HOLD", "EXIT", "CONSULT_AI"])

    # Test with missing position fields
    analysis = analyze_position(
        position={},  # Empty position
        quote={"price": 100, "volume": 50000},
        technicals={"rsi": 50},
        market="hkex"
    )
    test("Works with empty position dict", analysis is not None)

    # Test with very extreme values
    signals = detect_pnl_signals(-0.99, 0, 100, ctx, "hkex")  # -99%
    test("Handles extreme loss", len([s for s in signals if s.name == "stop_loss_hit"]) == 1)

    signals = detect_rsi_signals(100, ctx)  # Max RSI
    test("Handles RSI = 100", len([s for s in signals if s.name == "rsi_overbought"]) == 1)

    signals = detect_rsi_signals(0, ctx)  # Min RSI
    test("Handles RSI = 0", True)  # Should not crash

    # Test pattern_health with empty price history
    health = analyze_pattern_health([], {}, ctx)
    test("Pattern health with empty history", health is not None)
    test("higher_lows is False with empty history", health.get("higher_lows") == False)

    # Test different technical key formats
    technicals = {"ema9": 100, "sma20": 99}  # Without underscores
    signals = detect_trend_signals(101, technicals, ctx)
    test("Works with ema9/sma20 format", True)

    technicals = {"ema_9": 100, "sma_20": 99}  # With underscores
    signals = detect_trend_signals(101, technicals, ctx)
    test("Works with ema_9/sma_20 format", True)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
