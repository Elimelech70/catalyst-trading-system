# Current Issues and Future Considerations

**Last Updated**: 2025-12-11

---

## Active Issues

### 1. Orders Accepted but Not Filled
**Status**: Investigating
**Discovered**: 2025-12-11
**Severity**: Medium

All recent positions show `alpaca_status = 'accepted'` but `filled = 0`. Orders are being submitted to Alpaca but may not be executing.

**Possible Causes**:
- Limit orders not hitting target prices
- Paper trading behavior differences
- Order type configuration

**Action Required**:
- Check Alpaca dashboard for actual order status
- Verify order types (market vs limit)
- Review filled_quantity updates in trading service

---

### 2. Cron Startup Misconfiguration (FIXED)
**Status**: Resolved
**Discovered**: 2025-12-11
**Severity**: High

The cron job for starting Docker containers was missing the `cd` command, causing containers to not start from Dec 10-11.

**Root Cause**:
```bash
# BROKEN (was)
0 9 * * 1-5 docker-compose up -d >> /var/log/catalyst/startup.log 2>&1

# FIXED (now)
0 9 * * 1-5 cd /root/catalyst-trading-system && docker-compose up -d >> /var/log/catalyst/startup.log 2>&1
```

**Impact**: Missed 2 trading days (Dec 10-11 US time)

**Prevention**: Added to CLAUDE.md lessons learned

---

## Future Considerations

### 1. Position P&L Tracking
**Priority**: High

Current observations:
- `realized_pnl` and `unrealized_pnl` columns exist but are NULL
- `pnl_percent` not being calculated
- Need to implement position value updates from Alpaca

**Implementation Ideas**:
- Periodic sync with Alpaca positions API
- Calculate P&L on position close
- Add scheduled job to update unrealized P&L

---

### 2. Alpaca Order Status Sync
**Priority**: High

Need to sync local `positions.alpaca_status` with actual Alpaca order status:
- `accepted` → `filled` transition not being captured
- `filled_avg_price` not being updated
- Consider webhook or polling mechanism

---

### 3. Timezone Handling in Cron
**Priority**: Medium

Current setup:
- Server runs in Perth (AWST, UTC+8)
- Cron times are server-local
- US market hours are EST (UTC-5)

**Consideration**:
- 9 AM Perth = 8 PM EST (previous day)
- 5 PM Perth = 4 AM EST
- Current schedule may not align perfectly with market hours

**Possible Fix**: Use explicit timezone in cron or calculate offsets

---

### 4. Order Fill Confirmation
**Priority**: Medium

Before opening new positions, should verify:
- Previous orders actually filled
- Not duplicating positions in same symbol
- Account has sufficient buying power

---

### 5. Position Exit Strategy
**Priority**: Medium

Current state:
- Positions are opened but exit logic unclear
- `stop_loss` and `take_profit` columns exist but usage unknown
- No evidence of automated position closing

**Questions**:
- When/how are positions closed?
- Are stop losses being monitored?
- Is there EOD position cleanup?

---

### 6. Reporting Service GitHub Updates
**Status**: BROKEN
**Priority**: High

Report generation is failing with: `DATABASE_URL environment variable is required`

**Evidence**:
- Last report generated: 2025-12-09
- Missing reports: Dec 10, 11
- Cron sources .env but script still fails

**Current Cron**:
```bash
30 17 * * 1-5 cd /root/catalyst-trading-system && source .env && python3 scripts/generate-daily-report.py
```

**Action Required**:
- Fix environment variable loading in generate-daily-report.py
- Verify DATABASE_URL is exported properly
- Test report generation manually
- Confirm git push is working after report generates

---

### 7. Weekend/Holiday Handling
**Priority**: Low

Current cron runs Mon-Fri (server time), but:
- US holidays not accounted for
- Weekend transitions between timezones could cause issues

---

## Monitoring Improvements

### Suggested Alerts
1. No trading activity for > 24 hours during market days
2. Docker containers not running during market hours
3. High number of rejected orders
4. P&L thresholds (daily loss limits)

### Health Check Gaps
- Current health check only pings risk-manager
- Should verify all services
- Should check database connectivity
- Should verify Alpaca API access

---

## Technical Debt

1. **docker-compose.yml version attribute** - Marked obsolete, should remove
2. **Startup log confusion** - Shows "no configuration file provided" warnings
3. **Order table missing** - Referenced in queries but doesn't exist (orders tracked in positions table)

---

## Notes

- Review this document weekly
- Move resolved issues to a "Resolved" section with dates
- Prioritize based on trading impact
