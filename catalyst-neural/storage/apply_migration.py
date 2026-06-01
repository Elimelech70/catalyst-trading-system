"""
Apply a SQL migration file to the catalyst_neural.db.

Idempotency: ALTER TABLE in SQLite isn't IF NOT EXISTS-aware before 3.35;
we pre-check column existence via PRAGMA table_info and skip the ALTERs
that have already been applied. CREATE TABLE IF NOT EXISTS and CREATE INDEX
IF NOT EXISTS handle themselves.

Usage:
    python storage/apply_migration.py storage/migrations/002_cohort_experiments.sql
"""

import re
import sys
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.database import get_connection, DB_PATH


def _column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _table_exists(conn, table):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return rows is not None


def apply(migration_path):
    migration_path = Path(migration_path)
    if not migration_path.exists():
        raise FileNotFoundError(migration_path)

    # Backup first
    backup = DB_PATH.parent / f"{DB_PATH.name}.pre-{migration_path.stem}-backup"
    if not backup.exists():
        print(f"Backing up DB to {backup}")
        shutil.copy2(DB_PATH, backup)
    else:
        print(f"Backup already exists at {backup} — not overwriting")

    sql = migration_path.read_text()
    conn = get_connection()

    # Split on top-level semicolons, ignore SQL comments
    stmts = [s.strip() for s in re.split(r";\s*\n", sql) if s.strip()]
    n_applied = 0
    n_skipped = 0
    for stmt in stmts:
        # Strip leading comment lines
        body = "\n".join(line for line in stmt.splitlines()
                         if line.strip() and not line.strip().startswith("--"))
        if not body.strip():
            continue

        # Idempotency check for ALTER TABLE ADD COLUMN
        m = re.match(r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+)", body, re.I)
        if m:
            table, column = m.group(1), m.group(2)
            if _column_exists(conn, table, column):
                print(f"  skipped: {table}.{column} already exists")
                n_skipped += 1
                continue

        try:
            conn.executescript(body + ";")
            short = body.split("\n")[0][:80]
            print(f"  applied: {short}")
            n_applied += 1
        except Exception as e:
            print(f"  ERROR on statement:\n    {body[:200]}\n    {e}")
            raise

    conn.commit()
    conn.close()
    print(f"\nMigration {migration_path.name}: {n_applied} applied, {n_skipped} skipped")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python storage/apply_migration.py <migration.sql>")
        sys.exit(1)
    apply(sys.argv[1])
