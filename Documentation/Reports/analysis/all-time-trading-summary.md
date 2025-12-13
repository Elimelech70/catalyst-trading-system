# All-Time Trading Summary

**Report Generated:** 2025-12-13 21:30 EST
**Account Type:** Paper Trading
**Trading Period:** October 11, 2025 - December 13, 2025

---

## Overall Statistics

| Metric | Value |
|--------|-------|
| Total Positions Created | 141 |
| Currently Open | 60 |
| Closed | 81 |
| Unique Symbols Traded | 77 |
| First Trade | Oct 11, 2025 |
| Last Trade | Dec 12, 2025 |

---

## Position Closure Analysis

| Close Reason | Count | % of Closed |
|--------------|-------|-------------|
| order_side_bug_v1.2.0_alpaca_rejected | 54 | 66.7% |
| order_side_bug_v1.2.0_pending_cancelled | 27 | 33.3% |
| Stop-loss triggered | 0 | 0% |
| Take-profit triggered | 0 | 0% |
| Manual close | 0 | 0% |

**Note:** All 81 closed positions were due to the v1.2.0 order side bug, where "long" positions were incorrectly submitted as sells (shorts). These were cleaned up via the bug fix process, not actual trading exits.

---

## System Evolution

### Bug Fixes Timeline

| Date | Version | Issue Fixed |
|------|---------|-------------|
| Dec 3 | v1.1.0 | Sub-penny pricing (95% rejection rate) |
| Dec 5 | v1.2.0 | Order side bug ("long" → sell instead of buy) |
| Dec 6 | v1.3.0 | Order side validation & logging |
| Dec 13 | v1.4.0 | Bracket order submission |
| Dec 13 | v8.3.0 | Order sync, deduplication, limits |

### Trading Service Versions

| Version | Key Feature |
|---------|-------------|
| v5.0 | Initial production deployment |
| v8.0 | Alpaca integration |
| v8.1 | Sub-penny fix |
| v8.2 | Order side validation |
| v8.3 | Order sync + deduplication + limits |

---

## Current Open Positions (60 total)

### At Alpaca Broker (34 positions)
These 34 positions are held at Alpaca and queued for closure Monday.

| Count | Status |
|-------|--------|
| Filled orders | 34 |
| Total unrealized P&L | -$2,459.75 |
| Winners | 9 |
| Losers | 25 |

### Database-Only (26 positions)
These 26 positions exist in database but not at Alpaca (expired limit orders or unfilled).

---

## Symbols Traded (77 unique)

### Most Frequently Traded
Based on position count across all cycles:

| Symbol | Positions | Notes |
|--------|-----------|-------|
| QUBT | 6 | Quantum computing |
| NCLH | 5 | Cruise line |
| WBD | 5 | Media |
| LUMN | 4 | Telecom |
| ONDS | 4 | Tech |
| UAMY | 4 | Mining |
| STLA | 4 | Auto |
| TE | 4 | Biotech |
| UEC | 4 | Uranium |
| EOSE | 4 | Energy storage |

### Sector Distribution (Approximate)
- Technology: 25%
- Materials/Mining: 20%
- Consumer Discretionary: 15%
- Healthcare: 10%
- Energy: 10%
- Financials: 10%
- Other: 10%

---

## Key Learnings

### What Worked
1. Scanner identifying momentum stocks
2. Cron-based autonomous execution
3. Risk validation before trade submission
4. Logging and monitoring infrastructure

### What Didn't Work
1. Bracket orders silently failing (no stop-loss protection)
2. Order status never updating from Alpaca
3. Same symbol traded multiple times (no deduplication)
4. Position count growing unbounded across cycles

### Improvements Made
1. OrderClass.BRACKET now properly set
2. Background sync polls Alpaca every 60 seconds
3. Duplicate positions blocked at creation
4. 50 max total positions enforced

---

## Recommendations

### Short-term
1. Monitor bracket orders are executing correctly
2. Verify stop-losses trigger at expected prices
3. Track which symbols get rejected for duplication

### Medium-term
1. Add take-profit tracking in database
2. Implement trailing stops
3. Better scanner diversification (sector limits)

### Long-term
1. Machine learning for entry timing
2. Sentiment analysis integration
3. Portfolio-level risk management

---

## Report End
