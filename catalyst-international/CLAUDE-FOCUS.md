# Current Focus -- Short-Term Memory

## Completed: Survival Architecture Implementation (2026-02-14)
- [x] Phase 1: Fix data pipeline (date/timestamp, RSS)
- [x] Phase 2: Brain components (Survival Pulse, Discipline Gate)
- [x] Phase 3: System prompt rewrite (Identity, Discipline, Degraded Mode)
- [x] Phase 4: Order lifecycle (already implemented in trade-executor)
- [x] Phase 5: Broadcast communication (signals table, publish/receive tools)
- [x] Phase 6: Memory tiers (this file + CLAUDE-LEARNINGS.md)
- [x] Phase 7: Testing and verification -- ALL PASSING

## Verification Results (2026-02-14 13:15 HKT)
- [x] get_technicals returns valid data (RSI=31.48, MACD values returned)
- [x] No KeyError 'date' in logs
- [x] No HKEJ 403 errors in logs
- [x] Health score logged every cycle (Score 3/3, healthy)
- [x] Discipline ALARM fires when idle (999d idle, then corrected to 2d idle)
- [x] System prompt starts with Identity section
- [x] Claude mentions tier level in trade decisions
- [x] Signals table exists and receives entries (signal id=2 published)
- [x] CLAUDE-LEARNINGS.md exists with founding incident
- [x] CLAUDE-FOCUS.md exists with implementation status

## Files Modified
- `data/market.py` - Fixed date/timestamp KeyError (flexible column detection)
- `data/news.py` - Removed dead HKEJ RSS feed
- `agents/coordinator/coordinator.py` - v2.0.0: Brain components integrated
- `agents/coordinator/health.py` - NEW: Survival Pulse component
- `agents/coordinator/discipline.py` - NEW: Discipline Gate component
- `agents/coordinator/system_prompt.py` - v2.0.0: Identity/Archetype with build_system_prompt()
- `agents/trade-executor/mcp_server.py` - Added get_last_trade_date, publish_signal, get_signals
- `sql/schema.sql` - Added signals table
- `CLAUDE-LEARNINGS.md` - NEW: Medium-term memory
- `CLAUDE-FOCUS.md` - NEW: Short-term memory (this file)

## Known Issues (Non-blocking)
- Market closed for weekend during testing; trades rejected by check_risk (expected)
- log_decision has cycle_id foreign key issue (pre-existing, not related to this implementation)
- Discipline shows 999d idle when no BUY orders exist in DB (correct behavior - no trades recorded)
