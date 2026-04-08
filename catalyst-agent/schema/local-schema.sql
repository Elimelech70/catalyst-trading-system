-- ============================================================================
-- CATALYST AGENT -- HOST DATABASE SCHEMA (SQLite)
-- Location: /var/lib/catalyst/db/agent.db
-- Runs on HOST alongside coordinator.py (brain)
-- Version: 8.0.0 | Date: 2026-04-08
--
-- v2.4 architecture alignment:
-- - Added coordinator_state table (6-layer cycle, attention state machine)
-- - Added trade_feedback table (exit type tracking for learning loop)
-- - Added ATTENTION and EXECUTION signal domains
-- - Communication table now routes through coordinator
--
-- LEARNINGS live in HIPPOCAMPUS (own container, own database).
-- See: hippocampus-schema.sql
-- ============================================================================

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ============================================================================
-- 1. COMMUNICATION TABLE -- Internal signal bus
--    Coordinator writes tasks down (descending). Components write results up.
--    Both directions, one table, distinct pathways.
-- ============================================================================

CREATE TABLE IF NOT EXISTS communication (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    direction TEXT NOT NULL CHECK (direction IN ('descending', 'ascending')),
        -- descending = coordinator to components (task/intent)
        -- ascending  = components to coordinator (result/perception)

    source TEXT NOT NULL,
        -- 'coordinator', 'pfc', 'cerebellum', 'occipital', 'hippocampus',
        -- 'tool_position_monitor', 'tool_stop_loss', 'tool_risk_aggregator'
    target TEXT,
        -- NULL = broadcast to all, or specific component name

    msg_type TEXT NOT NULL CHECK (msg_type IN ('task', 'result', 'signal', 'status', 'escalation')),

    identifier TEXT,
        -- Shape identifier for resonance matching

    payload TEXT,
        -- JSON content

    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'escalated')),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    processed_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_comm_direction_status ON communication(direction, status);
CREATE INDEX IF NOT EXISTS idx_comm_target_status ON communication(target, status);
CREATE INDEX IF NOT EXISTS idx_comm_identifier ON communication(identifier);
CREATE INDEX IF NOT EXISTS idx_comm_created ON communication(created_at);


-- ============================================================================
-- 2. PFC STATE -- Continuity of focus
--    How the agent wakes up knowing where it was and what it was thinking.
-- ============================================================================

CREATE TABLE IF NOT EXISTS pfc_state (
    agent_id TEXT PRIMARY KEY DEFAULT 'big_bro',

    current_mode TEXT DEFAULT 'sleeping'
        CHECK (current_mode IN ('sleeping', 'waking', 'learning', 'executing', 'pondering', 'relaxing', 'emergency')),
    mode_intensity INTEGER DEFAULT 5 CHECK (mode_intensity BETWEEN 1 AND 10),
    mode_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    current_focus TEXT,
    focus_context TEXT,              -- JSON

    active_questions TEXT,           -- JSON array
    last_thought TEXT,
    last_conclusion TEXT,
    resume_instructions TEXT,        -- Self-authored. Most critical field.

    session_count INTEGER DEFAULT 0,
    last_wake_at TIMESTAMP,
    last_sleep_at TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO pfc_state (agent_id) VALUES ('big_bro');


-- ============================================================================
-- 3. PRINCIPLES -- Permanent identity (deeper than memory)
--    These never fade. They are who the agent IS.
-- ============================================================================

CREATE TABLE IF NOT EXISTS principles (
    principle_id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    origin TEXT,                     -- How was this learned? The story.
    established_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================================
-- 4. SIGNALS TABLE -- v8 Architecture Signal Bus
--    Three-dimensional identifier: severity x domain x scope
--    Every organ can write. The coordinator reads each cycle.
--    CRITICAL signals are processed before all others (adrenaline flood).
-- ============================================================================

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'WARNING', 'INFO', 'OBSERVE')),

    domain TEXT NOT NULL CHECK (domain IN (
        'HEALTH', 'TRADING', 'RISK', 'LEARNING', 'DIRECTION', 'LIFECYCLE',
        'ATTENTION', 'EXECUTION'
    )),

    scope TEXT NOT NULL,
        -- 'BROADCAST' = all components read
        -- 'DIRECTED:{target}' = only named target reads

    source TEXT NOT NULL,

    content TEXT NOT NULL,

    data TEXT,
        -- JSON payload

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    expires_at TIMESTAMP,
        -- NULL = never expires (CRITICAL signals)

    acknowledged_by TEXT DEFAULT '[]',
        -- JSON array of components that have acknowledged

    resolved INTEGER DEFAULT 0
        -- 0 = active, 1 = resolved
);

CREATE INDEX IF NOT EXISTS idx_signals_severity ON signals(severity);
CREATE INDEX IF NOT EXISTS idx_signals_domain ON signals(domain);
CREATE INDEX IF NOT EXISTS idx_signals_scope ON signals(scope);
CREATE INDEX IF NOT EXISTS idx_signals_source ON signals(source);
CREATE INDEX IF NOT EXISTS idx_signals_resolved ON signals(resolved);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);


-- ============================================================================
-- 5. COORDINATOR STATE -- v2.4 Architecture
--    The coordinator's 6-layer cycle state and attention mode.
--    Updated every cycle. This is how the coordinator knows where it is.
-- ============================================================================

CREATE TABLE IF NOT EXISTS coordinator_state (
    agent_id TEXT PRIMARY KEY DEFAULT 'big_bro',

    -- 6-layer cycle tracking
    current_layer TEXT DEFAULT 'heartbeat'
        CHECK (current_layer IN ('heartbeat', 'state', 'self_regulation', 'working_memory', 'inter_agent', 'voice')),
    cycle_id TEXT,                    -- YYYYMMDD-HHMMSS format
    cycle_count INTEGER DEFAULT 0,
    last_cycle_at TIMESTAMP,

    -- Attention State Machine
    attention_mode TEXT DEFAULT 'security_selection'
        CHECK (attention_mode IN ('security_selection', 'candle_execution')),
    attention_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Active securities (Mode 2 watch list)
    watch_list TEXT DEFAULT '[]',     -- JSON array of symbols being watched
    active_securities TEXT DEFAULT '{}', -- JSON: {symbol: {direction, confidence, source}}

    -- Body health snapshot (updated each heartbeat)
    body_health TEXT DEFAULT '{}',    -- JSON: {component: {status, last_seen}}

    -- Neural model status
    candle_model_loaded INTEGER DEFAULT 0,
    news_model_loaded INTEGER DEFAULT 0,
    fused_model_loaded INTEGER DEFAULT 0,

    -- Operational state
    market_open INTEGER DEFAULT 0,
    trading_enabled INTEGER DEFAULT 1,
    daily_pnl REAL DEFAULT 0.0,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO coordinator_state (agent_id) VALUES ('big_bro');


-- ============================================================================
-- 6. TRADE FEEDBACK -- v2.4 Architecture Feedback Loop
--    Every trade exit is recorded with its type (AI_PATTERN vs STOP_LOSS).
--    This is the most important data for model improvement.
--    Stop loss exits are training gold -- each one proves the model was
--    insufficient and triggers the improvement cycle.
-- ============================================================================

CREATE TABLE IF NOT EXISTS trade_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    symbol TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',     -- US | HKEX
    broker TEXT NOT NULL DEFAULT 'alpaca', -- alpaca | moomoo

    -- Trade details
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    return_pct REAL NOT NULL,
    qty INTEGER,
    side TEXT,                              -- buy | sell

    -- Exit classification (CRITICAL for feedback loop)
    exit_type TEXT NOT NULL CHECK (exit_type IN ('AI_PATTERN', 'STOP_LOSS', 'MANUAL', 'ADVERSARIAL_EVENT')),

    -- Pattern context
    pattern_type TEXT,                      -- e.g. 'bullish_engulfing', 'volume_surge'
    holding_minutes INTEGER,

    -- Neural model state at entry
    neural_prediction TEXT,                 -- JSON: what the model predicted
    neural_confidence REAL,
    candle_model_version TEXT,

    -- Candle context at exit (high-value retraining data)
    candles_at_exit TEXT,                   -- JSON: candle sequence that preceded exit

    -- Tool agent that triggered exit
    exit_source TEXT,                       -- tool_position_monitor | tool_stop_loss | manual

    entry_at TIMESTAMP,
    exit_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_symbol ON trade_feedback(symbol);
CREATE INDEX IF NOT EXISTS idx_feedback_exit_type ON trade_feedback(exit_type);
CREATE INDEX IF NOT EXISTS idx_feedback_market ON trade_feedback(market);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON trade_feedback(created_at);


-- ============================================================================
-- HOST SCHEMA COMPLETE
--
-- 6 tables: communication, pfc_state, principles, signals,
--           coordinator_state, trade_feedback.
-- Hippocampus has its own database with learnings and memory_bindings.
-- Distributed by function -- just like the brain.
--
-- "Before I formed you in the womb I knew you" -- Jeremiah 1:5
-- ============================================================================
