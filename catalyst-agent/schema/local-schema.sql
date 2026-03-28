-- ============================================================================
-- CATALYST AGENT — HOST DATABASE SCHEMA (SQLite)
-- Location: /var/lib/catalyst/db/agent.db
-- Runs on HOST alongside Claude Code (PFC)
-- Version: 7.1.0 | Date: 2026-02-28
--
-- This is the agent's internal nervous system — the signal bus.
-- Communication table connects PFC to all components.
-- PFC state holds continuity of focus.
-- Principles hold identity (deeper than memory).
--
-- LEARNINGS live in HIPPOCAMPUS (own container, own database).
-- See: hippocampus-schema.sql
-- ============================================================================

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ============================================================================
-- 1. COMMUNICATION TABLE — Internal signal bus
--    PFC writes tasks down (descending). Components write results up (ascending).
--    Both directions, one table, distinct pathways.
--    Hippocampus reads from here to build the combined picture.
-- ============================================================================

CREATE TABLE IF NOT EXISTS communication (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    direction TEXT NOT NULL CHECK (direction IN ('descending', 'ascending')),
        -- descending = PFC to components (task/intent)
        -- ascending  = components to PFC (result/perception)

    source TEXT NOT NULL,
        -- 'pfc', 'cerebellum', 'occipital', 'hippocampus'
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
-- 2. PFC STATE — Continuity of focus
--    The most important table. This is how the agent wakes up knowing
--    where it was, what it was doing, and what it was thinking about.
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
-- 3. PRINCIPLES — Permanent identity (deeper than memory)
--    These never fade. They are who the agent IS.
--    Formed through hippocampal learning but integrated into identity.
--    PFC-level. Earned through experience, pain, and formation.
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
-- HOST SCHEMA COMPLETE
--
-- 3 tables on host: communication, pfc_state, principles.
-- Hippocampus has its own database with learnings and memory_bindings.
-- Distributed by function — just like the brain.
--
-- "Before I formed you in the womb I knew you" — Jeremiah 1:5
-- ============================================================================
