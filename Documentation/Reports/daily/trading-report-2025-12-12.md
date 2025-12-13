# Daily Trading Report - December 12, 2025

**Report Date:** Thursday, December 12, 2025
**Report Generated:** 2025-12-13 21:45 EST
**Market Status:** Closed (report as of Friday close)
**Account Type:** Paper Trading

---

## Executive Summary

8 new positions opened across 2 trading cycles. All positions remain open with unrealized losses totaling approximately **-$680**. No bracket orders (stop-loss/take-profit) were active due to a bug discovered on Dec 13.

---

## Daily Statistics

| Metric | Value |
|--------|-------|
| Positions Opened | 8 |
| Positions Closed | 0 |
| Trading Cycles | 2 |
| Realized P&L | $0.00 |
| Unrealized P&L | ~-$680 |

---

## Positions Opened (Dec 12)

### Cycle 20251212-003 (12:00 AM ET - Market Open)

| Symbol | Side | Qty | Entry | Current* | Stop | Target | Unrealized P&L |
|--------|------|-----|-------|----------|------|--------|----------------|
| AG | long | 200 | $16.81 | $16.02 | $15.97 | $18.49 | -$158.00 |
| WVE | long | 200 | $16.75 | $16.68 | $15.91 | $18.43 | -$14.00 |
| NCLH | long | 200 | $20.55 | N/A** | $19.52 | $22.60 | N/A |
| EXK | long | 200 | $9.41 | $8.98 | $8.94 | $10.35 | -$86.00 |
| CCL | long | 200 | $27.84 | $27.65 | $26.45 | $30.62 | -$38.00 |

### Cycle 20251212-004 (2:00 AM ET - Extended Hours)

| Symbol | Side | Qty | Entry | Current* | Stop | Target | Unrealized P&L |
|--------|------|-----|-------|----------|------|--------|----------------|
| CLF | long | 200 | $13.41 | $12.71 | $12.74 | $14.75 | -$140.00 |
| LUV | long | 200 | $40.74 | N/A** | $38.70 | $44.81 | N/A |
| SOUN | long | 200 | $12.03 | $11.67 | $11.43 | $13.23 | -$72.00 |

*Current prices as of Friday Dec 13 close
**NCLH and LUV limit orders expired unfilled at Alpaca

---

## P&L Summary

| Symbol | Entry Value | Current Value | P&L | P&L % |
|--------|-------------|---------------|-----|-------|
| AG | $3,362 | $3,204 | -$158 | -4.7% |
| WVE | $3,350 | $3,336 | -$14 | -0.4% |
| EXK | $1,882 | $1,796 | -$86 | -4.6% |
| CCL | $5,568 | $5,530 | -$38 | -0.7% |
| CLF | $2,682 | $2,542 | -$140 | -5.2% |
| SOUN | $2,406 | $2,334 | -$72 | -3.0% |
| **Total** | **$19,250** | **$18,742** | **-$508** | **-2.6%** |

Note: NCLH ($4,110) and LUV ($8,148) limit orders expired - not included in totals.

---

## Trading Cycles

### Cycle 20251212-003
- **Start Time:** 12:00:02 AM ET
- **Mode:** normal
- **Status:** completed
- **Positions:** 5 (2 filled, 3 expired at Alpaca)

### Cycle 20251212-004
- **Start Time:** 2:00:02 AM ET
- **Mode:** normal
- **Status:** completed
- **Positions:** 3 (2 filled, 1 expired at Alpaca)

---

## Scanner Candidates

Symbols selected by scanner for Dec 12 trading:
- AG (First Majestic Silver) - Mining
- WVE (Wave Life Sciences) - Biotech
- NCLH (Norwegian Cruise Line) - Travel
- EXK (Endeavour Silver) - Mining
- CCL (Carnival Corporation) - Travel
- CLF (Cleveland-Cliffs) - Steel
- LUV (Southwest Airlines) - Airlines
- SOUN (SoundHound AI) - Technology

**Sector Distribution:**
- Mining/Materials: 3 (AG, EXK, CLF)
- Travel/Leisure: 2 (NCLH, CCL)
- Technology: 1 (SOUN)
- Healthcare: 1 (WVE)
- Airlines: 1 (LUV)

---

## Issues Noted

1. **Limit Order Expiration**: 3 of 8 orders expired without filling (NCLH x2 cycles, LUV)
   - Limit prices may have been set too aggressively

2. **No Stop-Loss Protection**: Bracket orders not submitting correctly
   - CLF down 5.2% would have triggered -5% stop in autonomous mode
   - Bug fixed in v1.4.0 (Dec 13)

3. **Duplicate Symbol**: NCLH selected in multiple cycles
   - Deduplication added in v8.3.0 (Dec 13)

---

## Risk Metrics

| Metric | Value |
|--------|-------|
| Total Exposure (filled) | $19,250 |
| Max Single Position | $5,568 (CCL) |
| Average Position Size | $3,208 |
| Worst Performer | CLF (-5.2%) |
| Best Performer | WVE (-0.4%) |

---

## Market Context

- US markets traded normally Thursday Dec 12
- Broad market slightly down
- Materials and mining sector weakness (AG, EXK, CLF all red)
- Travel sector mixed (CCL slight loss, NCLH order expired)

---

## Actions Taken (Dec 13)

1. All positions queued for closure Monday open
2. Bracket order bug fixed (v1.4.0)
3. Position deduplication added (v8.3.0)
4. Order status sync implemented (v8.3.0)

---

## Report End
