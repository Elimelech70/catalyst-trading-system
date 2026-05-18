
# Catalyst Repo Hygiene — Multi-Host Setup Checklist

**Name of Application:** Catalyst Trading System
**Name of file:** catalyst-repo-hygiene.md
**Version:** 1.0.0
**Created:** 2026-05-18
**Updated by:** Craig + Claude
**Purpose:** Pre-flight checklist for each host that will check out the
consolidated `catalyst-trading-system` repo. Ensures secrets are not
committed, large artifacts stay out of version control, and the multi-host
workflow does not produce merge conflicts. Run once per host before any
analysis or development work begins.

---

## REVISION HISTORY

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-05-18 | Initial checklist |

---

## CONTEXT — WHY THIS MATTERS

Three hosts will now share one repo:

| Host | What it owns | Primary edit zone |
|------|--------------|-------------------|
| Intl droplet | catalyst-international (active trader) | `catalyst-international/` |
| US droplet | catalyst-agent (stopped, archived) | `catalyst-agent/` (read-mostly) |
| Craig's laptop | catalyst-neural | `catalyst-neural/` |

Without discipline, three risks materialize fast:

1. **Secrets in the repo.** `.env` files contain Anthropic API keys, Alpaca
   keys, Moomoo credentials, database URLs. The project memory already
   notes credentials have been exposed in session once — a single careless
   `git add .` makes that permanent in repo history.
2. **Large artifacts bloat the repo.** PyTorch checkpoints, SQLite databases,
   CSV training data — none of these belong in Git. They make every clone
   slow and every push fragile.
3. **Merge conflicts on shared paths.** If two hosts edit `Documentation/`
   or top-level config at the same time, conflicts are guaranteed.

This checklist addresses all three. Run it on each host BEFORE doing any
analysis work.

---

## SCOPE BOUNDARY

This document is hygiene only. It does not change application behaviour,
does not modify trading logic, does not touch databases. It only changes
`.gitignore`, verifies no secrets are staged, and establishes ownership
rules. If anything in this checklist appears to demand changes to running
systems, stop and consult Craig.

---

## SECTION 1 — UNIVERSAL `.gitignore` (RUN ON ONE HOST, COMMIT, PULL ON OTHERS)

This is the canonical `.gitignore` for the root of `catalyst-trading-system`.
Run this on one host (intl is fine), commit, then pull on the others before
they do any work.

### 1.1 Inspect what's already ignored

```bash
cd /root/catalyst-trading-system   # or ~/catalyst-trading-system on laptop

# Show current ignore file (may not exist)
cat .gitignore 2>/dev/null || echo "No .gitignore at repo root"

# Show subdirectory ignores too
find . -name ".gitignore" -not -path "*/\.git/*" 2>/dev/null
```

### 1.2 Write the canonical root `.gitignore`

Append rather than overwrite — preserve anything project-specific that's
already there. Compare existing entries to the list below; add what's
missing.

```bash
cat >> .gitignore << 'GITIGNORE_EOF'

# ============================================================================
# CATALYST REPO HYGIENE — added 2026-05-18
# Do not remove without consulting Craig
# ============================================================================

# --- Secrets (NEVER commit) ---
.env
.env.*
!.env.example
*.env
secrets.yaml
secrets.json
credentials.json
*_credentials.*

# --- Python ---
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
env/
ENV/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
*.egg-info/
build/
dist/

# --- Jupyter ---
.ipynb_checkpoints/
*.ipynb_checkpoints

# --- Local databases (catalyst-agent SQLite, anything similar) ---
*.db
*.sqlite
*.sqlite3
*.db-journal
*.db-wal
*.db-shm

# --- Model artifacts (catalyst-neural) ---
*.pt
*.pth
*.pkl
*.joblib
*.h5
*.hdf5
*.onnx
*.ckpt
*.safetensors
models/checkpoints/
models/saved/
checkpoints/

# --- Training data (large, regenerable) ---
data/raw/
data/processed/
data/cache/
*.parquet
*.feather
# Allow small reference CSVs but block large ones (review case-by-case)
# *.csv

# --- Logs ---
logs/
*.log
*.log.*
nohup.out

# --- OS / editor ---
.DS_Store
Thumbs.db
.vscode/
.idea/
*.swp
*.swo
*~

# --- Node (in case any sub-component uses it) ---
node_modules/
.npm
.next/

# --- Backup / temp ---
*.bak
*.backup
*.tmp
*.orig
~$*

# ============================================================================
# END CATALYST REPO HYGIENE
# ============================================================================
GITIGNORE_EOF

# De-duplicate (in case some lines already existed)
sort -u .gitignore -o .gitignore.dedup && mv .gitignore.dedup .gitignore

# Review
cat .gitignore
```

### 1.3 Verify the ignore rules work

```bash
# Should print "ignored" for each of these test paths
git check-ignore -v .env                          2>/dev/null && echo ".env: ignored ✓"
git check-ignore -v catalyst-neural/model.pt      2>/dev/null && echo "*.pt: ignored ✓"
git check-ignore -v catalyst-agent/var/agent.db   2>/dev/null && echo "*.db: ignored ✓"
git check-ignore -v __pycache__/foo.pyc           2>/dev/null && echo "pycache: ignored ✓"
git check-ignore -v venv/bin/python               2>/dev/null && echo "venv: ignored ✓"
```

**STOP CONDITION:** If any of these do NOT print "ignored", the `.gitignore`
is broken. Inspect, fix, re-test before proceeding.

### 1.4 Commit and push

```bash
git add .gitignore
git status   # confirm ONLY .gitignore is staged

git diff --cached .gitignore   # review the diff one more time

git commit -m "Add canonical repo-hygiene .gitignore for multi-host setup

Covers secrets (.env), Python artifacts, local SQLite databases,
ML model checkpoints, training data caches, logs, and editor cruft.
Run on intl droplet first; other hosts pull before working."

git push origin main
```

---

## SECTION 2 — PER-HOST PRE-WORK CHECKLIST

**Run on every host before starting any work in the repo.** Takes ~5 minutes.

### 2.1 Pull latest

```bash
cd <repo-path>   # /root/catalyst-trading-system or ~/catalyst-trading-system

# Confirm we're on the right remote
git remote -v
# Expected: origin pointing to the canonical catalyst-trading-system repo

# Confirm branch
git branch --show-current
# Expected: main (or whatever your default is)

# Pull
git pull origin main

# STOP CONDITION: If pull fails due to local commits, do not force-push.
# Stash, inspect, decide before continuing:
#   git stash list
#   git status
```

### 2.2 Scan for secrets that may have been staged

This is the single most important check.

```bash
# Look for any .env file the repo is tracking
git ls-files | grep -E '(\.env$|\.env\.|env\.|credentials|secrets)' \
  | grep -v '\.env\.example$'

# Expected output: EMPTY. If anything prints, that file is tracked.
```

**STOP CONDITION:** If ANY tracked `.env` or credentials file shows up:

```bash
# Untrack the file (keeps it on disk, removes from index)
git rm --cached <path-to-tracked-secret-file>

# Add to .gitignore if not already covered
echo "<path-to-tracked-secret-file>" >> .gitignore

# Commit the removal
git add .gitignore
git commit -m "Untrack accidentally-committed secrets file"
git push origin main

# THEN: rotate every credential that was in that file.
# The fact that it was removed does NOT remove it from git history.
# Anyone with repo access still has access to all previous commits.
```

### 2.3 Scan working tree for unstaged secrets

```bash
# Find every .env in the working tree
find . -name ".env*" -not -path "./.git/*" -not -name "*.example" 2>/dev/null

# These should exist on disk but NOT be tracked. Verify:
for f in $(find . -name ".env*" -not -path "./.git/*" -not -name "*.example" 2>/dev/null); do
  if git ls-files --error-unmatch "$f" 2>/dev/null; then
    echo "❌ TRACKED: $f"
  else
    echo "✓ Untracked: $f"
  fi
done
```

Every result should be `✓ Untracked`. If anything shows `❌ TRACKED`, follow
the untrack procedure from 2.2.

### 2.4 Verify large/binary artifacts aren't sneaking in

```bash
# Anything over 5MB currently tracked
git ls-files | xargs -I{} sh -c 'test -f "{}" && du -h "{}" 2>/dev/null' \
  | awk '$1 ~ /M|G/ {print}' \
  | sort -rh | head -20

# If anything large shows, investigate. Common offenders:
# - Trained model checkpoints (.pt, .pkl)
# - Training data CSVs / parquets
# - SQLite databases that aren't in .gitignore
# - PDF reports that should be in Documentation/Reports/ not committed
```

### 2.5 Confirm `.env.example` exists (template without secrets)

For each component (catalyst-agent, catalyst-international, catalyst-neural):

```bash
for component in catalyst-agent catalyst-international catalyst-neural; do
  if [ -d "$component" ]; then
    if [ -f "$component/.env.example" ]; then
      echo "✓ $component/.env.example exists"
    else
      echo "⚠ $component/.env.example MISSING — create one with keys but blank values"
    fi
  fi
done
```

If any are missing, create them. Example pattern for a `.env.example`:

```bash
# catalyst-international/.env.example
DATABASE_URL=
RESEARCH_DATABASE_URL=
ANTHROPIC_API_KEY=
MOOMOO_HOST=
MOOMOO_PORT=
MOOMOO_TRADE_PWD=
```

Variable names but no values. This is the documentation of what each
component needs without exposing what they actually are.

### 2.6 Confirm git identity is set correctly on this host

```bash
git config user.name
git config user.email

# If wrong or unset, set them. Use a consistent identity across hosts
# so commits from intl droplet, US droplet, and laptop are attributable:
#   git config --global user.name "Craig"
#   git config --global user.email "<your-email>"
```

---

## SECTION 3 — OWNERSHIP RULES (CONVENTIONS, NOT ENFORCEMENT)

Git has no way to enforce who touches what. These are conventions to avoid
conflicts. Treat them as house rules.

### 3.1 Edit zones per host

| Host | Primary edit zone | Read-only |
|------|-------------------|-----------|
| Intl droplet | `catalyst-international/` | everything else |
| US droplet | `catalyst-agent/` (currently archive only) | everything else |
| Laptop | `catalyst-neural/`, `Documentation/Design/`, anything that lives only on laptop | everything else |
| Any host | `Documentation/Analysis/` (append-only — new files, rarely edit existing) | — |

### 3.2 Cross-cutting files (who edits them)

| File | Who edits | Notes |
|------|-----------|-------|
| Root `.gitignore` | Anyone, but coordinate | Pull-then-edit-then-push, no parallel edits |
| Root `CLAUDE.md` | Laptop (design context) | This is the architect-facing doc |
| `Documentation/Design/*.md` | Laptop primarily | Design docs flow from architect |
| `Documentation/Analysis/*.md` | Whichever host produced the analysis | Append-only convention |
| `Documentation/Reports/daily/*.md` | The droplet that generated the report | Each droplet writes to its own date-stamped file |

### 3.3 Pull-before-work, push-after-work

Always. Every session, on every host.

```bash
# Session start:
git pull origin main

# Work happens here…

# Session end (if changes were made):
git status
git add <specific files only — never `git add .` casually>
git diff --cached    # review every change
git commit -m "<descriptive message>"
git push origin main
```

**STOP CONDITION:** If `git status` shows files you don't recognize, stop.
Investigate before staging.

### 3.4 If two hosts edit the same file the same day

Whoever pushes second will get a rejection. Resolve with:

```bash
git pull --rebase origin main
# Resolve any conflicts shown
git add <resolved files>
git rebase --continue
git push origin main
```

**Do not use `git push --force` on `main` ever.** If you find yourself
considering it, stop and ask.

---

## SECTION 4 — ONE-TIME AUDIT OF EXISTING REPO HISTORY

After the new `.gitignore` is in place, do a one-time check that nothing
sensitive is already in the repo's history (which `.gitignore` won't help
with — `.gitignore` only stops new commits, doesn't clean old ones).

### 4.1 Search history for credential-like patterns

```bash
cd <repo-path>

# Anthropic key prefix
git log -p --all -S "sk-ant-" | head -50

# Alpaca key prefix (typical PK pattern)
git log -p --all -S "PK" --pickaxe-regex | grep -E '^[+-].*PK[A-Z0-9]{16,}' | head -20

# Postgres URLs with embedded passwords
git log -p --all -S "postgres://" | grep -E '^\+.*postgres://[^:]+:[^@]+@' | head -20

# Generic .env content
git log --all --diff-filter=A --name-only | grep -E '\.env$' | sort -u
```

**STOP CONDITION:** If any of these surface real credentials in git history:

1. **Rotate the credential immediately** — assume it is compromised the moment
   it entered git history, even if the repo is private. Anthropic API key,
   database password, Alpaca keys, Moomoo credentials — all of them.
2. **Document the rotation** in `Documentation/Analysis/credential-rotation-2026-05-18.md`
   so the rest of the family knows the keys changed.
3. **Decide whether to scrub history** (`git filter-repo` or BFG Repo-Cleaner)
   AFTER rotation. Scrubbing is destructive and not strictly required if the
   credentials are rotated, but it does remove the embarrassment trail.

This step matches the existing concern in the project memory:
*"Live credentials were inadvertently displayed in a session — Anthropic API
key, database password, and Alpaca keys should be rotated."*

If those have not been rotated yet, **rotate them now regardless of what
this audit finds.** A credential displayed in a Claude session is already
exposed.

---

## SECTION 5 — VERIFICATION CHECKLIST PER HOST

After completing Sections 1–4, run this final verification. Every line
should print a ✓.

```bash
cd <repo-path>

echo "=== Catalyst Repo Hygiene Verification ==="
echo ""

# 1. On main, clean working tree
[ "$(git branch --show-current)" = "main" ] \
  && echo "✓ On main branch" \
  || echo "❌ Not on main: $(git branch --show-current)"

[ -z "$(git status --porcelain)" ] \
  && echo "✓ Working tree clean" \
  || echo "❌ Uncommitted changes present"

# 2. .gitignore covers secrets
git check-ignore .env >/dev/null 2>&1 \
  && echo "✓ .env in .gitignore" \
  || echo "❌ .env NOT in .gitignore"

# 3. No tracked secrets
if git ls-files | grep -qE '(\.env$|credentials|secrets)' | grep -v example; then
  echo "❌ Secrets tracked in repo"
else
  echo "✓ No tracked secret files"
fi

# 4. Git identity set
[ -n "$(git config user.email)" ] \
  && echo "✓ Git user.email set: $(git config user.email)" \
  || echo "❌ Git user.email not configured"

# 5. Remote points somewhere
[ -n "$(git remote -v | grep origin)" ] \
  && echo "✓ Remote 'origin' configured" \
  || echo "❌ No origin remote"

echo ""
echo "=== End verification ==="
```

If all five print ✓, the host is ready for work.

---

## SECTION 6 — QUICK REFERENCE

### Before any work session

```bash
cd <repo-path>
git pull origin main
git status   # should be clean
```

### After any work session

```bash
git status                          # see what changed
git add <specific files>            # never `git add .` casually
git diff --cached                   # review staged diff
git commit -m "<descriptive>"
git push origin main
```

### If something looks wrong

Stop. Don't force, don't push. Ask Craig.

---

## SECTION 7 — IF SECRETS LEAK ANYWAY

It happens. The protocol if a secret reaches the repo:

1. **Rotate first, scrub second.** Always. The key is compromised the moment
   it's committed, even if the commit is reverted seconds later.
2. **Rotation order:** Anthropic API key → Alpaca keys → Moomoo credentials
   → database passwords. Most exposed first.
3. **Update `.env` on every host** with the new credentials.
4. **Restart any running services** (catalyst-international agent, etc.) so
   they pick up the new credentials.
5. **Optional: scrub history** with `git filter-repo --invert-paths --path
   <file>`. Requires every host to re-clone afterward.
6. **Document the incident** in `Documentation/Analysis/` so the family
   knows what happened and what changed.

The point isn't to be perfect — it's to recover fast when imperfect happens.

---

**END OF CHECKLIST v1.0.0**

*Catalyst Trading System — Repo Hygiene*
*Craig + Claude — 2026-05-18*
*"Secrets out, signal in."*
