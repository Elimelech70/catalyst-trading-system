# Repository Cleanup Implementation Guide

**Name of Application:** Catalyst Trading System  
**Name of file:** repository-cleanup-implementation.md  
**Version:** 1.0.0  
**Last Updated:** 2025-12-27  
**Purpose:** Remove deprecated files and placeholder scripts from the repository

---

## REVISION HISTORY

**v1.0.0 (2025-12-27)** - Initial cleanup implementation
- Remove deprecated documentation (old/ and Archive/ folders)
- Remove placeholder scripts that were never implemented
- Remove one-time setup scripts no longer needed

---

## Executive Summary

This document provides step-by-step instructions for Claude Code to clean up the catalyst-trading-system GitHub repository by removing deprecated, superseded, and placeholder files.

**Total files to remove:** 10  
**Total folders to remove:** 2  
**Risk level:** ✅ Low (all items explicitly deprecated or placeholder)

---

## Phase 1: Remove Deprecated Documentation Folders

### 1.1 Remove `Documentation/Design/old/` Folder

**Reason:** All files superseded by v7.0.0 documents

**Files contained:**
- `database-schema-mcp-v60.md` → Replaced by `database-schema.md` v7.0.0
- `architecture-mcp-v60.md` → Replaced by `architecture.md` v7.0.0
- `catalyst-functional-spec-v6.1.0b.md` → Replaced by `functional-specification.md` v7.0.0

**Command:**
```bash
cd /root/catalyst-trading-system
rm -rf Documentation/Design/old/
git add -A
git commit -m "chore: Remove deprecated Documentation/Design/old/ folder (superseded by v7.0.0)"
```

### 1.2 Remove `catalyst-international/Documentation/Implementation/Archive/` Folder

**Reason:** All files explicitly marked as DEPRECATED or superseded

**Files contained:**
- `IBKR_IBeam_Implementation_Plan.md` → Header states "DEPRECATED - SUPERSEDED BY IBGA"
- `IMPLEMENTATION-GUIDE.md` → Old implementation guide, replaced by current docs

**Command:**
```bash
cd /root/catalyst-trading-system
rm -rf catalyst-international/Documentation/Implementation/Archive/
git add -A
git commit -m "chore: Remove deprecated catalyst-international Archive folder (IBKR superseded by Moomoo/Futu)"
```

---

## Phase 2: Remove Placeholder Scripts

### 2.1 Remove Placeholder Scripts in `scripts/`

**Reason:** These scripts contain only `echo "This is a placeholder"` and were never implemented. Real implementations exist elsewhere.

| Script | Content | Replacement |
|--------|---------|-------------|
| `emergency-stop.sh` | Placeholder only | `production-manager.sh stop` |
| `recover-system.sh` | Placeholder only | `production-manager.sh restart` |
| `manage.sh` | Placeholder only | `production-manager.sh` |
| `service_diagnostic.sh` | Placeholder only | `trade_watchdog.py` (Doctor Claude) |

**Command:**
```bash
cd /root/catalyst-trading-system

# Remove placeholder scripts
rm -f scripts/emergency-stop.sh
rm -f scripts/recover-system.sh
rm -f scripts/manage.sh
rm -f scripts/service_diagnostic.sh

git add -A
git commit -m "chore: Remove placeholder scripts (never implemented, real versions exist)"
```

---

## Phase 3: Remove One-Time Setup Scripts

### 3.1 Remove `create_catalyst_structure.sh`

**Reason:** One-time folder structure generator. The structure now exists and is maintained manually.

**Command:**
```bash
cd /root/catalyst-trading-system
rm -f create_catalyst_structure.sh
git add -A
git commit -m "chore: Remove create_catalyst_structure.sh (one-time setup, structure exists)"
```

---

## Phase 4: Push Changes

**Command:**
```bash
cd /root/catalyst-trading-system
git push origin main
```

---

## Complete Script (All Phases)

For convenience, here is a single script that performs all cleanup:

```bash
#!/bin/bash
# Repository Cleanup Script
# Generated: 2025-12-27
# Purpose: Remove deprecated files and placeholder scripts

set -e  # Exit on error

cd /root/catalyst-trading-system

echo "=== Phase 1: Remove Deprecated Documentation ==="

# 1.1 Remove old/ folder
if [ -d "Documentation/Design/old" ]; then
    rm -rf Documentation/Design/old/
    echo "✓ Removed Documentation/Design/old/"
else
    echo "⚠ Documentation/Design/old/ not found (already removed?)"
fi

# 1.2 Remove Archive/ folder
if [ -d "catalyst-international/Documentation/Implementation/Archive" ]; then
    rm -rf catalyst-international/Documentation/Implementation/Archive/
    echo "✓ Removed catalyst-international/Documentation/Implementation/Archive/"
else
    echo "⚠ Archive folder not found (already removed?)"
fi

echo ""
echo "=== Phase 2: Remove Placeholder Scripts ==="

# Remove placeholder scripts
for script in emergency-stop.sh recover-system.sh manage.sh service_diagnostic.sh; do
    if [ -f "scripts/$script" ]; then
        rm -f "scripts/$script"
        echo "✓ Removed scripts/$script"
    else
        echo "⚠ scripts/$script not found (already removed?)"
    fi
done

echo ""
echo "=== Phase 3: Remove One-Time Setup Scripts ==="

if [ -f "create_catalyst_structure.sh" ]; then
    rm -f create_catalyst_structure.sh
    echo "✓ Removed create_catalyst_structure.sh"
else
    echo "⚠ create_catalyst_structure.sh not found (already removed?)"
fi

echo ""
echo "=== Phase 4: Commit and Push ==="

git add -A
git status

echo ""
echo "Files staged for removal. Committing..."

git commit -m "chore: Repository cleanup - remove deprecated docs and placeholder scripts

Removed:
- Documentation/Design/old/ (superseded by v7.0.0 docs)
- catalyst-international/Documentation/Implementation/Archive/ (IBKR deprecated)
- scripts/emergency-stop.sh (placeholder)
- scripts/recover-system.sh (placeholder)
- scripts/manage.sh (placeholder)
- scripts/service_diagnostic.sh (placeholder, replaced by trade_watchdog.py)
- create_catalyst_structure.sh (one-time setup script)

All removed items were either:
1. Explicitly marked DEPRECATED/SUPERSEDED in headers
2. Placeholder scripts containing only echo statements
3. One-time setup scripts no longer needed"

git push origin main

echo ""
echo "=== Cleanup Complete ==="
echo "Repository has been cleaned up and changes pushed to GitHub."
```

---

## Verification

After cleanup, verify the following files/folders **still exist** (should NOT be removed):

### Scripts to KEEP:
- `scripts/trade_watchdog.py` ✓
- `scripts/log_activity.py` ✓
- `scripts/doctor_claude_monitor.sh` ✓
- `scripts/production-manager.sh` ✓
- `scripts/health-check.sh` ✓

### Documentation to KEEP:
- `Documentation/Design/architecture.md` (v7.0.0) ✓
- `Documentation/Design/database-schema.md` (v7.0.0) ✓
- `Documentation/Design/functional-specification.md` (v7.0.0) ✓
- `CLAUDE.md` ✓

### Verification Commands:
```bash
# Verify key files still exist
ls -la scripts/trade_watchdog.py
ls -la scripts/production-manager.sh
ls -la Documentation/Design/architecture.md
ls -la CLAUDE.md

# Verify removed items are gone
ls Documentation/Design/old/ 2>&1 | grep -q "No such file" && echo "✓ old/ removed"
ls catalyst-international/Documentation/Implementation/Archive/ 2>&1 | grep -q "No such file" && echo "✓ Archive/ removed"
```

---

## Rollback (If Needed)

If anything goes wrong, rollback with:

```bash
cd /root/catalyst-trading-system
git reset --hard HEAD~1
git push --force origin main
```

---

**END OF IMPLEMENTATION GUIDE**

*Generated by Claude Desktop*  
*Catalyst Trading System*  
*December 27, 2025*
