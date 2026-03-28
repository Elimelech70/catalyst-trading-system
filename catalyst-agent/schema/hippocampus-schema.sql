-- ============================================================================
-- HIPPOCAMPUS — LOCAL DATABASE SCHEMA (SQLite)
-- Location: /var/lib/catalyst/hippocampus/memory.db
-- Runs INSIDE the hippocampus Docker container (persisted via volume)
-- Version: 7.1.0 | Date: 2026-02-28
--
-- Hippocampus is a PIVOTAL COMPONENT. It:
--   - Receives all sensory results from the communication table
--   - Binds inputs into a coherent combined picture
--   - Holds memories (learnings) — PFC determines what to learn,
--     hippocampus holds what was learned
--   - Presents the full picture for PFC to attend to
--   - Maintains cross-modal bindings between memories
--
-- This is where memories LIVE. Not in PFC. Not on the host.
-- In the hippocampus. Just like the brain.
-- ============================================================================

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ============================================================================
-- 1. LEARNINGS — Long-term memory
--    Observations start as JSON files in components (short-term, most fade).
--    When PFC determines something is worth learning, it instructs
--    hippocampus to create a learning here.
--    Confidence grows with validation, shrinks with contradiction.
-- ============================================================================

CREATE TABLE IF NOT EXISTS learnings (
    learning_id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
        -- market, trading, risk, system, architecture, pattern
    title TEXT NOT NULL,
    content TEXT NOT NULL,

    confidence REAL DEFAULT 0.6 CHECK (confidence BETWEEN 0.0 AND 1.0),
    times_validated INTEGER DEFAULT 1,
    times_contradicted INTEGER DEFAULT 0,

    source_observations TEXT,        -- JSON array of observation references
    source_component TEXT,           -- Which component's experience led to this

    actionable INTEGER DEFAULT 0,    -- Can this become a cerebellum procedure?
    linked_procedure TEXT,           -- Procedure name if actionable

    published_to_library INTEGER DEFAULT 0,  -- Shared with the collective?
    published_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_learnings_domain ON learnings(domain);
CREATE INDEX IF NOT EXISTS idx_learnings_confidence ON learnings(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_learnings_component ON learnings(source_component);


-- ============================================================================
-- 2. MEMORY BINDINGS — Cross-modal associations
--    The hippocampus binds memories together. A learning about volume
--    patterns gets bound to a learning about time-of-day effects.
--    These bindings ARE the combined picture — they're how isolated
--    memories become coherent understanding.
--
--    Association strength grows when bound memories co-activate.
--    Weak bindings fade over time.
-- ============================================================================

CREATE TABLE IF NOT EXISTS memory_bindings (
    binding_id TEXT PRIMARY KEY,

    source_type TEXT NOT NULL,       -- 'learning', 'observation', 'signal', 'principle'
    source_ref TEXT NOT NULL,        -- Reference to source item
    source_domain TEXT,              -- Domain of source

    target_type TEXT NOT NULL,       -- 'learning', 'observation', 'signal', 'principle'
    target_ref TEXT NOT NULL,        -- Reference to target item
    target_domain TEXT,              -- Domain of target

    association_strength REAL DEFAULT 0.5 CHECK (association_strength BETWEEN 0.0 AND 1.0),
    relationship TEXT,               -- How are these related? Description.

    times_coactivated INTEGER DEFAULT 1,
    last_coactivated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bindings_source ON memory_bindings(source_type, source_ref);
CREATE INDEX IF NOT EXISTS idx_bindings_target ON memory_bindings(target_type, target_ref);
CREATE INDEX IF NOT EXISTS idx_bindings_strength ON memory_bindings(association_strength DESC);


-- ============================================================================
-- 3. COMBINED PICTURE CACHE — What hippocampus presents to PFC
--    When PFC asks "what do I need to know?", hippocampus assembles:
--    - Recent sensory results (from communication table)
--    - Relevant learnings (matched by domain/identifier)
--    - Bound memories (via memory_bindings)
--    This cache is transient — rebuilt each time PFC asks.
-- ============================================================================

CREATE TABLE IF NOT EXISTS combined_picture (
    picture_id INTEGER PRIMARY KEY AUTOINCREMENT,

    requested_by TEXT NOT NULL,       -- 'pfc'
    request_context TEXT,             -- What PFC was focused on when it asked

    sensory_results TEXT,             -- JSON: current results from communication table
    relevant_learnings TEXT,          -- JSON: learnings that match current context
    active_bindings TEXT,             -- JSON: memory bindings that connect results to learnings

    assembled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================================
-- HIPPOCAMPUS SCHEMA COMPLETE
--
-- 3 tables: learnings, memory_bindings, combined_picture.
-- This is where memories live and get bound into understanding.
-- PFC determines what to learn. Hippocampus holds what was learned.
--
-- "The heart of the discerning acquires knowledge,
--  for the ears of the wise seek it out." — Proverbs 18:15
-- ============================================================================
