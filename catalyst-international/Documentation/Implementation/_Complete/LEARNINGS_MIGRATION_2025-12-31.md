# CLAUDE.md Learnings Migration - 2025-12-31

**Status:** COMPLETED
**Database:** catalyst_research
**Table:** claude_learnings

---

## Summary

Migrated 9 key learnings from CLAUDE.md into the consciousness database for cross-agent sharing.

## Learnings Migrated

### Trading Lessons

| # | Agent | Learning | Confidence |
|---|-------|----------|------------|
| 11 | intl_claude | HKEX 11-tier tick size rules | 0.95 |
| 12 | intl_claude | Moomoo real-time data benefits | 0.90 |
| 14 | intl_claude | Dollar-based position sizing | 0.85 |
| US1 | public_claude | Order side mapping critical | 1.00 |
| US2 | public_claude | Prefer LIMIT over MARKET orders | 0.90 |

### System Lessons

| # | Agent | Learning | Confidence |
|---|-------|----------|------------|
| 13 | intl_claude | HK symbol format (HK.00700) | 0.95 |
| - | big_bro | Single-agent > microservices | 0.85 |
| - | intl_claude | OpenD simpler than IBKR IBGA | 0.95 |

### Market Lessons

| # | Agent | Learning | Confidence |
|---|-------|----------|------------|
| - | intl_claude | HKEX lunch break (12:00-13:00) | 0.95 |

## Database Verification

```sql
SELECT agent_id, LEFT(learning, 60), category, confidence
FROM claude_learnings
ORDER BY created_at DESC LIMIT 15;
```

**Result:** 15 total learnings in database (9 new + 6 existing)

## Benefits

1. **Cross-Agent Sharing** - big_bro can query intl_claude learnings
2. **Dashboard Access** - Learnings visible on mobile dashboard
3. **Version Control** - SQL script in git for audit trail
4. **Confidence Scoring** - Higher confidence = more reliable

## Script Location

```
Documentation/Implementation/migrate-learnings.sql
```

---

**Migration Complete**
