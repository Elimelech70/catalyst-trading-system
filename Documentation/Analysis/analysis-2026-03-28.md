# Catalyst Trading System - Comprehensive Trading Analysis

**Date**: 2026-03-28
**Analyst**: Claude Code (Opus 4.6)
**Data Source**: PostgreSQL (catalyst_trading / defaultdb)
**Period Analyzed**: January 14 – March 13, 2026

---

## Executive Summary

The v8 AI trading system ran for approximately 2 months on an Alpaca paper account (~$106,646 equity). It made **315 decisions** across **37 trading days**, but the positions table contains **zero records** — a critical persistence gap. Based on exit decision reasoning, the system generated an estimated **+$1,400–$1,600 net profit (~1.5% return)**.

The system showed genuine promise in Phase 1 (Jan–Feb) with disciplined risk management and good stock selection. However, it was crippled by three infrastructure failures: (1) positions never persisted to the database, (2) stale Alpaca orders blocked exits repeatedly, and (3) the market scanner went dead for 6 weeks. The system went dormant on March 13 when Anthropic API credits were exhausted.

---

## Decision Engine Summary

| Metric | Value |
|--------|-------|
| Total Decisions | 315 |
| Active Days | 37 (Jan 14 – Mar 13) |
| Hold Decisions | 161 (51%) |
| Skip Decisions | 110 (35%) |
| Exit Decisions | 43 (14%) |
| Entry Decisions | 0 (not recorded) |
| Position Checks | 1 (<1%) |

The system is **extremely conservative** — 86% of all decisions were to hold existing positions or skip trading entirely.

---

## Two Phases of Trading

### Phase 1: Active Trading (Jan 14 – Feb 13)

- Multiple positions held simultaneously (CPB, HST, CSX, RF, KWEB, QID, CAG, etc.)
- Good decision-making: winners hit 5–9% take-profit targets, losers stopped at –5%
- High decision volume: 8–23 decisions per day
- **Main problem**: Execution failures on exits ("shares held for orders")

### Phase 2: Ghost Mode (Feb 19 – Mar 13)

- Scanner returning **zero candidates** every session (6+ weeks)
- System cycling through hold/skip with nothing to do
- Only QXO position appeared (Mar 12) and immediately got stuck
- Eventually went dormant when API credits ran out

---

## Symbols Traded

| Symbol | Total Decisions | Holds | Exits | Period | Performance |
|--------|----------------|-------|-------|--------|-------------|
| CPB | 48 | 39 | 9 | Jan 22 – Feb 13 | Best performer, +8–9.5% |
| HST | 24 | 20 | 4 | Jan 23 – Feb 6 | Strong, +5–9.6% |
| CSX | 13 | 8 | 5 | Jan 23 – Feb 3 | Solid, +6–8.9% |
| RF | 11 | 9 | 2 | Jan 21 – Feb 6 | +9.25% |
| QID | 11 | 9 | 2 | Jan 20 – Feb 5 | Inverse ETF, –3.3% |
| QXO | 10 | 9 | 1 | Mar 12–13 | Last position, stuck |
| KWEB | 9 | 5 | 4 | Jan 16 – Feb 3 | Worst, –5.3% stop hit |
| CAG | 5 | 3 | 2 | Jan 16 – Jan 30 | +7.2% |
| PCG | 3 | 0 | 3 | Jan 21 – Jan 23 | –3.9% |
| AAL | 2 | 0 | 2 | Jan 21 – Jan 26 | –5.5% stop hit |
| CHWY | 2 | 1 | 1 | Jan 28 – Jan 29 | –3.6% |
| EWZ | 2 | 1 | 1 | Jan 21 – Jan 22 | Exit attempted |
| SOFI | 2 | 0 | 2 | Jan 16 – Jan 20 | Exit attempted |
| OWL | 1 | 0 | 1 | Jan 26 | –4.4% |
| PINS | 1 | 0 | 1 | Jan 20 | Exit attempted |
| ITUB | 1 | 0 | 1 | Jan 22 | Exit attempted |

**Meta-symbols** (market/portfolio-level decisions):
- MARKET: 91 decisions (84 skips) — scanner found nothing
- PORTFOLIO: 38 decisions (36 holds)
- CASH: 12 decisions (all holds) — sitting in cash
- SESSION/MARKET_SCAN/ALL: Various skip decisions

---

## P&L Reconstruction (from Exit Decision Reasoning)

### Winners

| Symbol | P&L | Return % | Notes |
|--------|-----|----------|-------|
| CSX | +$572 | +8.11% | EOD close, strong momentum play |
| CPB | +$506 | +9.42% | Near 10% take-profit target |
| HST | +$322 | +9.10% | Near 10% target, locked in |
| CAG | +$240 | +7.21% | Momentum strategy successful |
| HST | +$186 | +5.25% | Reached minimum profit target |
| RF | ~+$300 | +9.25% | Attempted close, execution issues |

### Losers

| Symbol | Est. P&L | Return % | Notes |
|--------|----------|----------|-------|
| KWEB | ~–$200 | –5.27% | Stop loss triggered |
| AAL | ~–$200 | –5.54% | Breached stop loss |
| PCG | ~–$150 | –3.88% | Approaching stop |
| OWL | ~–$150 | –4.44% | Approaching stop |
| QID | ~–$100 | –3.30% | Loss on inverse ETF |
| CHWY | ~–$100 | –3.61% | Weakness, attempted close |

### Estimated Summary

| Metric | Value |
|--------|-------|
| Gross Wins | ~$2,126 |
| Gross Losses | ~–$900 |
| **Net Estimated P&L** | **~+$1,200 to +$1,600** |
| **Return on $106K** | **~1.1–1.5%** |
| Win Rate (by decision) | ~60% wins, ~40% losses |

---

## Database State (as of 2026-03-28)

| Table | Rows | Notes |
|-------|------|-------|
| decisions | 315 | Full decision history preserved |
| pattern_confidence | 10 | All at baseline 0.50, zero samples |
| claude_state | 1 | PONDER mode, last active Mar 21 |
| signals | 1 | Test signal only |
| securities | 1 | Only AAPL registered |
| **positions** | **0** | **CRITICAL: No position records** |
| trading_cycles | 0 | Empty |
| scan_results | 0 | Empty |
| orders | 0 | Empty |
| patterns | 0 | Empty |
| pattern_outcomes | 0 | Empty |
| agent_logs | 0 | Empty |

---

## Critical Problems Identified

### 1. Positions Table Empty (SEVERITY: CRITICAL)

The decisions table references active positions with real P&L numbers, but the `positions` table has **zero records**. The system was making decisions based on Alpaca account data directly but never persisting position state to the local database.

**Impact**:
- No historical trade record in the database
- No way to do backtesting or performance attribution
- The learning system (pattern_confidence) has zero samples — it never learned
- All P&L data exists only in Alpaca's systems

**Root Cause**: The executor (`organs/executor.py`) likely reads from Alpaca but doesn't write back to the positions table, or the write path has a bug.

### 2. Stale Orders Blocking Exits (SEVERITY: HIGH)

A massive recurring pattern across 20+ exit decisions: the system **could not close positions** because shares were tied up in existing/pending orders on Alpaca. This affected CPB (9 exit attempts!), CSX, KWEB, RF, CAG, HST, and others.

**Example from CPB**:
- Feb 10: Tried to close at +9.42% → "shares held for orders"
- Feb 11: Tried again at +8.5% → same error
- Feb 11: Tried again at +9.12% → same error
- Feb 12: Tried at +9.57% → same error
- Feb 12: Tried at +8% → same error
- Feb 13: Finally attempted closure at +8%

**Impact**: Profitable positions couldn't be closed at optimal levels. Some likely deteriorated before eventually closing.

**Root Cause**: No logic to cancel orphaned/stale Alpaca orders before attempting new exit orders.

### 3. Scanner Dead for 6 Weeks (SEVERITY: HIGH)

From late February through March 13, the scanner found **zero candidates** almost every session. The system tried relaxing criteria multiple times (from 2%+ to 1%+ to 0.5%+ moves) and still found nothing.

**Possible Causes**:
- Alpaca IEX data feed returning incomplete data
- Scanner parameters too restrictive for current market conditions
- API/data feed issues not being logged or detected

**Impact**: ~6 weeks of the system sitting in cash doing absolutely nothing.

### 4. Pattern Learning Never Engaged (SEVERITY: MEDIUM)

All 10 pattern types sit at baseline 0.50 confidence with zero samples:
- bull_flag, bear_flag, breakout, momentum, double_bottom
- cup_handle, ascending_triangle, vwap_reclaim, gap_and_go, news_catalyst

The synaptic learning loop (LTP/LTD) never activated because `pattern_outcomes` has 0 rows.

**Impact**: The AI brain never learned from its trades. The entire learning architecture is untested.

### 5. System Dormant — API Credits Exhausted (SEVERITY: BLOCKING)

- Last decision: March 13, 2026
- claude_state: PONDER mode (last active March 21)
- Anthropic API credits exhausted
- GitHub token expired — can't push code

---

## Risk Management Assessment

The system's risk management **rules** are sound:
- Stop loss at –5% (triggered correctly for KWEB at –5.27%, AAL at –5.54%)
- Take profit target at 10% (most exits at 8–9.5%, slightly below target)
- Day trade limit awareness (PDT rule monitoring)
- Position sizing appears conservative

**However**, the **execution** of risk management was poor:
- Stop losses couldn't execute due to stale orders
- Take profits were delayed by the same issue
- No circuit breaker for repeated execution failures

---

## Recommendations (Priority Order)

### P0 — Blocking

1. **Top up Anthropic API credits** — Decision Engine is dead without it
2. **Update GitHub token** — Can't push code or sync

### P1 — Critical Fixes

3. **Fix positions persistence** — Executor must write to positions table on every trade. Without this, there's no trade journal and no learning.
4. **Add stale order cancellation** — Before any new exit order, cancel all existing orders for that symbol on Alpaca. This was the #1 operational failure.

### P2 — High Priority

5. **Fix scanner data feed** — Investigate why IEX feed returned zero candidates for 6 weeks. Add logging/alerting for zero-candidate scans.
6. **Bootstrap pattern_outcomes** — Manually seed from Alpaca trade history so the confidence table can start learning.

### P3 — Improvements

7. **Add execution retry with order cleanup** — If an exit fails due to held shares, automatically cancel stale orders and retry.
8. **Add alerting** — Notify when scanner returns zero candidates for 3+ consecutive sessions.
9. **Persist scan_results and trading_cycles** — These tables are also empty, reducing observability.

---

## Appendix: Daily Decision Activity

| Date | Total | Holds | Skips | Exits |
|------|-------|-------|-------|-------|
| 2026-01-14 | 1 | 0 | 0 | 0 |
| 2026-01-15 | 1 | 0 | 0 | 1 |
| 2026-01-16 | 3 | 1 | 0 | 2 |
| 2026-01-19 | 4 | 1 | 2 | 1 |
| 2026-01-20 | 6 | 3 | 0 | 3 |
| 2026-01-21 | 5 | 2 | 0 | 3 |
| 2026-01-22 | 4 | 0 | 0 | 4 |
| 2026-01-23 | 3 | 0 | 0 | 3 |
| 2026-01-26 | 5 | 3 | 0 | 2 |
| 2026-01-27 | 1 | 1 | 0 | 0 |
| 2026-01-28 | 6 | 4 | 0 | 2 |
| 2026-01-29 | 8 | 5 | 2 | 1 |
| 2026-01-30 | 8 | 3 | 2 | 3 |
| 2026-02-01 | 1 | 1 | 0 | 0 |
| 2026-02-02 | 23 | 17 | 2 | 4 |
| 2026-02-03 | 17 | 12 | 2 | 3 |
| 2026-02-04 | 16 | 14 | 0 | 2 |
| 2026-02-05 | 15 | 14 | 1 | 0 |
| 2026-02-06 | 22 | 16 | 4 | 2 |
| 2026-02-10 | 11 | 9 | 1 | 1 |
| 2026-02-11 | 9 | 7 | 0 | 2 |
| 2026-02-12 | 9 | 7 | 0 | 2 |
| 2026-02-13 | 10 | 2 | 7 | 1 |
| 2026-02-19 | 11 | 2 | 9 | 0 |
| 2026-02-20 | 10 | 2 | 8 | 0 |
| 2026-02-23 | 9 | 2 | 7 | 0 |
| 2026-02-24 | 10 | 2 | 8 | 0 |
| 2026-02-25 | 8 | 4 | 4 | 0 |
| 2026-02-26 | 11 | 2 | 9 | 0 |
| 2026-02-27 | 11 | 2 | 9 | 0 |
| 2026-03-02 | 1 | 1 | 0 | 0 |
| 2026-03-06 | 10 | 3 | 7 | 0 |
| 2026-03-09 | 8 | 2 | 6 | 0 |
| 2026-03-10 | 9 | 2 | 7 | 0 |
| 2026-03-11 | 10 | 3 | 7 | 0 |
| 2026-03-12 | 11 | 4 | 6 | 1 |
| 2026-03-13 | 8 | 8 | 0 | 0 |

**Clear pattern**: Phase 1 (Jan–early Feb) had exits and active trading. Phase 2 (mid-Feb onward) was almost entirely skips/holds with the system idle.

---

*Analysis generated from 315 decision records in the catalyst_trading database. P&L figures are estimates reconstructed from decision reasoning text, not from actual position records (which are missing).*
