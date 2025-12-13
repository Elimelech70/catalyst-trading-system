# Weekly Trading Report - Week 50, 2025

**Report Period:** December 7-13, 2025
**Report Generated:** 2025-12-13 21:30 EST
**Account Type:** Paper Trading

---

## Executive Summary

This week saw consistent trading activity but all positions remain open due to missing bracket order functionality. A critical bug was discovered where stop-loss and take-profit orders were not being submitted to Alpaca, leaving positions without automatic risk management.

**Key Actions Taken:**
- All 34 open positions queued for closure (executes Monday 9:30 AM EST)
- Fixed bracket order submission bug (v1.4.0)
- Implemented order status sync (v8.3.0)
- Added position deduplication
- Added total position limit (50 max)

---

## Weekly Position Summary

| Date | Positions Opened | Still Open | Closed | Realized P&L |
|------|------------------|------------|--------|--------------|
| Dec 12 | 8 | 8 | 0 | $0.00 |
| Dec 11 | 13 | 13 | 0 | $0.00 |
| Dec 9 | 6 | 6 | 0 | $0.00 |
| Dec 8 | 15 | 15 | 0 | $0.00 |
| Dec 7 | 7 | 7 | 0 | $0.00 |
| **Total** | **49** | **49** | **0** | **$0.00** |

---

## Portfolio Status at Week End (Friday Close)

| Metric | Value |
|--------|-------|
| Open Positions | 34 (at Alpaca) |
| Total Market Value | $114,969.98 |
| Total Cost Basis | $117,429.73 |
| **Unrealized P&L** | **-$2,459.75** |
| Account Equity | $95,829.20 |
| Win Rate | 26.5% (9 winners, 25 losers) |

---

## Top Performers

| Symbol | P&L | P&L % |
|--------|-----|-------|
| MRNA | +$333.38 | +6.0% |
| AAPL | +$152.64 | +37.9% |
| HPE | +$138.00 | +3.0% |
| QXO | +$136.00 | +3.3% |
| AEO | +$93.16 | +1.9% |

## Worst Performers

| Symbol | P&L | P&L % |
|--------|-----|-------|
| AAOI | -$564.08 | -8.1% |
| LYFT | -$435.04 | -9.7% |
| PATH | -$368.68 | -9.6% |
| UAMY | -$300.00 | -11.8% |
| RGTI | -$275.64 | -5.0% |

---

## Trading Cycles This Week

| Cycle ID | Date (ET) | Mode | Positions |
|----------|-----------|------|-----------|
| 20251212-004 | Dec 12 02:00 | normal | 3 |
| 20251212-003 | Dec 12 00:00 | normal | 5 |
| 20251212-002 | Dec 11 22:00 | normal | 4 |
| 20251212-001 | Dec 11 20:30 | normal | 4 |
| 20251211-002 | Dec 11 02:00 | normal | 3 |
| 20251211-001 | Dec 11 00:00 | normal | 2 |
| 20251209-004 | Dec 9 02:00 | normal | 3 |
| 20251209-003 | Dec 9 00:00 | normal | 3 |
| 20251209-002 | Dec 8 22:00 | normal | 3 |
| 20251209-001 | Dec 8 20:30 | normal | 5 |

---

## Issues Identified & Fixed

### 1. Bracket Orders Not Submitting (FIXED)
- **Root Cause:** Missing `order_class=OrderClass.BRACKET` parameter
- **Impact:** All stop-loss and take-profit orders ignored by Alpaca
- **Fix:** alpaca_trader.py v1.4.0

### 2. Order Status Not Syncing (FIXED)
- **Root Cause:** No background polling mechanism
- **Impact:** Database showed 'accepted' when orders were actually 'filled'
- **Fix:** trading-service.py v8.3.0 - 60-second sync task

### 3. Duplicate Positions (FIXED)
- **Root Cause:** No check for existing open position
- **Impact:** Multiple positions in same symbol (NCLH x3, WBD x3, etc.)
- **Fix:** trading-service.py v8.3.0 - deduplication check

### 4. Position Limit (FIXED)
- **Root Cause:** Only per-cycle limit, not total limit
- **Impact:** Positions accumulated to 34 across cycles
- **Fix:** trading-service.py v8.3.0 - 50 max total positions

---

## Lessons Learned

1. **Always verify order class is set** - Alpaca silently ignores bracket parameters without order_class
2. **Implement status polling** - Cannot rely on initial submission status
3. **Deduplicate at database level** - Workflow can send same symbol multiple times
4. **Global position limits essential** - Per-cycle limits insufficient

---

## Next Week Plan

1. Verify bracket orders working with test trades
2. Monitor order status sync accuracy
3. Review scanner candidate selection to reduce duplicates
4. Consider tighter stop-losses (currently -5% autonomous)

---

## Report End
