-- ============================================================================
-- MIGRATE CLAUDE.MD LEARNINGS TO CONSCIOUSNESS DATABASE
-- Run on: catalyst_research database
-- Date: 2025-12-31
-- Purpose: Move valuable learnings from CLAUDE.md into claude_learnings table
-- ============================================================================

-- Lesson 11: HKEX Tick Size Compliance
INSERT INTO claude_learnings (agent_id, learning, category, confidence, context)
VALUES (
    'intl_claude',
    'HKEX has 11-tier tick size rules. Incorrect prices are rejected. Always round prices using _round_to_tick() before submission. Tiers: <0.25=0.001, <0.50=0.005, <10=0.01, <20=0.02, <100=0.05, etc.',
    'trading',
    0.95,
    'Implemented in brokers/futu.py:440-479. Discovered during HKEX integration. Critical for order acceptance.'
);

-- Lesson 12: Moomoo Real-Time Data Benefits
INSERT INTO claude_learnings (agent_id, learning, category, confidence, context)
VALUES (
    'intl_claude',
    'Moomoo provides real-time HKEX data (unlike IBKR 15-min delay). Can use both MARKET and LIMIT orders, tighter stops, and volume-based signals are reliable. Still prefer LIMIT orders for better fills.',
    'trading',
    0.90,
    'Migration from IBKR to Moomoo Dec 2025. Real-time data included with account. Major improvement over delayed data trading.'
);

-- Lesson 13: HK Symbol Format
INSERT INTO claude_learnings (agent_id, learning, category, confidence, context)
VALUES (
    'intl_claude',
    'Futu/Moomoo uses "HK.00700" format internally. Always use _format_hk_symbol() to convert user input (e.g., "700" -> "HK.00700"). Strip leading zeros when displaying back to user.',
    'system',
    0.95,
    'Implemented in brokers/futu.py. Essential for API calls. User says "700", API needs "HK.00700".'
);

-- Lesson 14: Dollar-Based Position Sizing
INSERT INTO claude_learnings (agent_id, learning, category, confidence, context)
VALUES (
    'intl_claude',
    'Use dollar-based position sizing, not share-based. Target 15-20% of portfolio per position. Formula: quantity = int(target_value / price / lot_size) * lot_size. HKEX lot size typically 100 shares.',
    'trading',
    0.85,
    'Gap identified in analysis. Share-based sizing creates uneven exposure. Dollar-based ensures consistent risk per position.'
);

-- US Lesson 1: Order Side Mapping (shared learning)
INSERT INTO claude_learnings (agent_id, learning, category, confidence, context)
VALUES (
    'public_claude',
    'CRITICAL: Order side mapping must be explicit. BUY is not always 1. Different APIs use different conventions. Always verify mapping in broker client code. Bug caused inverted trades in US system.',
    'trading',
    1.0,
    'First error-free autonomous trade Dec 29, 2025. 10 major bugs fixed including this. Maps: Alpaca uses OrderSide.BUY/SELL enum.'
);

-- US Lesson: Limit Orders Preferred
INSERT INTO claude_learnings (agent_id, learning, category, confidence, context)
VALUES (
    'public_claude',
    'ALWAYS prefer LIMIT orders over MARKET orders. Market orders risk slippage, especially in volatile momentum stocks. Set limit slightly above ask for buys, below bid for sells.',
    'trading',
    0.90,
    'Documented best practice. Especially critical when using delayed data or trading illiquid stocks.'
);

-- Cross-Market Learning: Architecture Simplicity
INSERT INTO claude_learnings (agent_id, learning, category, confidence, context)
VALUES (
    'big_bro',
    'Single-agent architecture (intl_claude) proved more reliable than 8-service microservices (US). ~1000 lines vs 5000+ lines. $6/mo vs $24/mo. Simpler debugging. Consider refactoring US to match.',
    'system',
    0.85,
    'International system Dec 2025. Fresh start without legacy. AI agent handles complexity that microservices encoded. Every decision logged with reasoning.'
);

-- Cross-Market Learning: OpenD vs Docker
INSERT INTO claude_learnings (agent_id, learning, category, confidence, context)
VALUES (
    'intl_claude',
    'Moomoo OpenD gateway is far simpler than IBKR IBGA. No Docker, no Java, no VNC, no 2FA issues. Native binary with auto-reconnect. Migration from IBKR to Moomoo eliminated entire class of gateway problems.',
    'system',
    0.95,
    'IBKR migration Dec 2025. IBKR required Docker + Java 17 + JavaFX + VNC + constant 2FA failures. OpenD just works.'
);

-- Trading Hours Learning
INSERT INTO claude_learnings (agent_id, learning, category, confidence, context)
VALUES (
    'intl_claude',
    'HKEX has lunch break 12:00-13:00. CLOSE all positions before lunch. Morning session 09:30-12:00, afternoon 13:00-16:00. Perth (AWST) is same timezone, enables daytime trading.',
    'market',
    0.95,
    'HKEX market structure. Lunch break is liquidity gap - do not hold through it. Perth alignment was key reason for choosing HKEX over other Asian markets.'
);

-- Verify inserts
SELECT agent_id, LEFT(learning, 60) as learning_preview, category, confidence 
FROM claude_learnings 
ORDER BY created_at DESC 
LIMIT 15;
