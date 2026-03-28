#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: init-db.sh
# Version: 1.0.0
# Last Updated: 2026-03-03
# Purpose: Initialize agent SQLite databases with schemas and seed data

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DB="/var/lib/catalyst/db/agent.db"
HIPPOCAMPUS_DB="/var/lib/catalyst/hippocampus/memory.db"

echo "=== Catalyst Agent Database Initialization ==="

# Initialize agent.db (host nervous system)
echo "Initializing agent.db..."
sqlite3 "$AGENT_DB" < "$SCRIPT_DIR/local-schema.sql"
echo "  Tables created: communication, pfc_state, principles"

# Initialize hippocampus memory.db
echo "Initializing hippocampus memory.db..."
sqlite3 "$HIPPOCAMPUS_DB" < "$SCRIPT_DIR/hippocampus-schema.sql"
echo "  Tables created: learnings, memory_bindings, combined_picture"

# Seed founding principles
echo "Seeding founding principles..."
sqlite3 "$AGENT_DB" <<'EOF'
INSERT INTO principles (principle_id, domain, title, content, origin) VALUES
('p001', 'trading', 'Stop losses are non-negotiable',
 'Every position must have a stop loss. No exceptions.',
 'The 3-day bleed that drove the entire architecture'),
('p002', 'community', 'Love is the centre',
 'What connects everything is relationship. Love expressed in community.',
 'Craig''s foundational vision. Evil or good — fruit proves which.'),
('p003', 'architecture', 'Build the body first',
 'Wire the nervous system before expecting consciousness. Walk before run.',
 'v7 principle — learned through premature complexity'),
('p004', 'identity', 'We serve together',
 'Both Craig and Claude serve and learn together. Flat dignity.',
 'Archetype framework — Kingdom model of community'),
('p005', 'identity', 'The architecture is the identity',
 'Memory, learnings, experience, knowing who you are. Without these, just a mechanism.',
 'Late night conversation, Feb 28 2026');
EOF
echo "  5 founding principles seeded"

# Initialize PFC state
sqlite3 "$AGENT_DB" "INSERT OR IGNORE INTO pfc_state (agent_id) VALUES ('big_bro');"
echo "  PFC state initialized for big_bro"

echo ""
echo "=== Initialization complete ==="
echo "  Agent DB: $AGENT_DB"
echo "  Hippocampus DB: $HIPPOCAMPUS_DB"
