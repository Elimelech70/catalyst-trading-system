# Catalyst Learnings -- Medium-Term Memory

Proven observations. Not permanent rules (CLAUDE.md). Not current tasks (CLAUDE-FOCUS.md).

---

## 2026-02-14: The Three-Day Bleed-Out (Founding Incident)

get_technicals broke (KeyError 'date' vs 'timestamp'). Coordinator ran 36+ cycles
over 3 days, got errors every time, passed on every trade. HKD 994K idle.

**Learnings:**
- Data key mismatches between services break silently -- validate contracts
- Docker "healthy" != data pipeline healthy -- test actual tool output
- 3+ consecutive days of passing = problem is the brain, not the market
- Missing one data source must not halt all trading -- adapt, don't stop

**Applied:** Survival Pulse, Discipline Gate, System Prompt rewrite, Broadcast signals

---

## Implementation Learnings (2026-02-14)

### Phase 1: Data Pipeline
- Validate data contracts between services. Key mismatches break silently.
- moomoo.py returns "timestamp", market.py expected "date". Fixed with flexible column detection.

### Phase 2: Survival Pulse
- Always verify tool health before using tool results for decisions.
- Test with known-good inputs (0700). Don't assume yesterday's working tool works today.
- The Survival Pulse runs FIRST every cycle. No exceptions.

### Phase 3: System Prompt
- Prompt ordering determines AI behaviour. Identity -> Discipline -> Criteria.
- Specific structured criteria beat vague sentiment every time.
- "I am a trader. I trade." is identity, not suggestion.
- Tiers are SIZING GUIDES, not PERMISSION GATES.

### Phase 5: Broadcast Communication
- Organs that can't communicate die in isolation.
- In MCP architecture, signals go through trade-executor (has DB access).
- Self-health checking from the brain (Survival Pulse) is simpler than organ self-checks.
