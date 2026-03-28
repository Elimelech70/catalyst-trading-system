# Droplet Cleanup & GitHub Update

**Name of Application**: Catalyst Trading System  
**Name of file**: droplet-cleanup-and-github-update.md  
**Version**: 1.0.0  
**Created**: 2026-03-29  
**Author**: Craig + Claude  
**Purpose**: Step-by-step instructions for little_bro to clean up the prod droplet and add catalyst-agent to GitHub  

---

## REVISION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| v1.0.0 | 2026-03-29 | Initial guide |

---

## CONTEXT

The prod droplet has accumulated several old directory attempts at the trading system. We have confirmed via crontab and systemd audit that only these directories are load-bearing:

- `/root/catalyst-trading-system/` — cron home, master .env, consciousness, dev_claude
- `/root/catalyst-agent/` — live brain containers (hippocampus, occipital, cerebellum)
- `/root/claude-code-viewer/` — running viewer tool

Everything else is safe to archive. Additionally, `catalyst-agent/` has never been in GitHub — this task adds it to the `catalyst-trading-system` repo as a subfolder.

---

## PRE-FLIGHT CHECKS

Run these before starting. All should pass.

```bash
# Brain containers are healthy
docker compose -f /root/catalyst-agent/docker-compose.yml ps
# Expected: catalyst-hippocampus, catalyst-occipital, catalyst-cerebellum — all Up (healthy)

# Cron is active
crontab -l | grep catalyst-trading-system
# Expected: multiple lines referencing /root/catalyst-trading-system

# Git repo is clean
cd /root/catalyst-trading-system && git status
# Expected: nothing to commit, or only CLAUDE.md if not yet pushed
```

---

## STEP 1: Archive Dead Directories

These directories have been confirmed inactive — not in crontab, not in Docker, not referenced anywhere live.

```bash
mkdir -p ~/catalyst-backups/archived-$(date +%Y%m%d)

mv ~/catalyst-dev ~/catalyst-backups/archived-$(date +%Y%m%d)/
mv ~/catalyst-us ~/catalyst-backups/archived-$(date +%Y%m%d)/
mv ~/catalyst ~/catalyst-backups/archived-$(date +%Y%m%d)/
mv ~/catalyst-dev.archived.20260117 ~/catalyst-backups/archived-$(date +%Y%m%d)/
```

**Verify:**
```bash
ls ~/
# Expected: catalyst-agent  catalyst-backups  catalyst-trading-system  claude-code-viewer  crontab-backup-20251216-165408.txt  docker-inventory.md  snap
```

---

## STEP 2: Convert catalyst-agent/.env to Symlink

The `.env` in `catalyst-agent/` is currently a real file containing live credentials. It must be a symlink to the master credentials file in `catalyst-trading-system/` — both so credentials are managed in one place and so the file is never accidentally committed to GitHub.

```bash
rm ~/catalyst-agent/.env
ln -s /root/catalyst-trading-system/.env ~/catalyst-agent/.env
```

**Verify:**
```bash
ls -la ~/catalyst-agent/.env
# Expected: /root/catalyst-agent/.env -> /root/catalyst-trading-system/.env

# Confirm brain containers still work (they read .env at runtime)
docker compose -f /root/catalyst-agent/docker-compose.yml ps
# Expected: all three containers still Up (healthy)
```

⚠️ **If containers go unhealthy after this step — stop and alert Craig before proceeding.**

---

## STEP 3: Copy catalyst-agent into the Repo

```bash
cp -r ~/catalyst-agent ~/catalyst-trading-system/catalyst-agent
```

Add a `.gitignore` to exclude credentials, SQLite databases, compiled files and logs:

```bash
cat > ~/catalyst-trading-system/catalyst-agent/.gitignore << 'EOF'
# Credentials — never commit
.env

# SQLite nervous system — lives on droplet only
*.db
*.db-shm
*.db-wal

# Python
__pycache__/
*.pyc
*.pyo
*.pyd

# Logs
logs/
*.log
EOF
```

**Verify the .env is excluded:**
```bash
cd ~/catalyst-trading-system
git status catalyst-agent/
# Confirm: catalyst-agent/.env does NOT appear in the output
# If it does appear — STOP. Do not proceed to Step 4.
```

---

## STEP 4: Commit and Push to GitHub

```bash
cd ~/catalyst-trading-system

# Stage catalyst-agent
git add catalyst-agent/

# Review exactly what is being committed
git status
# Confirm: no .env, no .db files, no .pyc files

# Commit
git commit -m "feat: add catalyst-agent brain architecture to repository

- coordinator.py: v8 brain with 6-layer consciousness cycle
- hippocampus: memory binding Docker container
- occipital: pattern recognition Docker container  
- cerebellum: procedure execution + Alpaca broker Docker container
- shared/: db.py, models.py, config.py modules
- docker-compose.yml: brain container orchestration
- .gitignore: excludes .env, SQLite DBs, pycache, logs"

git push
```

**Verify:**
```bash
git log --oneline -3
# Expected: most recent commit is the feat: add catalyst-agent commit
```

---

## STEP 5: Docker Cleanup

Remove 52 dangling images (~21.4 GB), build cache (796 MB), and orphaned volumes from the retired microservices era.

```bash
# Remove dangling images
docker image prune -f

# Remove build cache
docker builder prune -f

# Remove orphaned microservices volumes
docker volume rm \
  catalyst-news-logs \
  catalyst-orchestration-logs \
  catalyst-pattern-logs \
  catalyst-redis-data \
  catalyst-reporting-logs \
  catalyst-risk-logs \
  catalyst-scanner-logs \
  catalyst-technical-logs \
  catalyst-trading-logs \
  catalyst-workflow-logs
```

**Verify — only expected resources should remain:**
```bash
# Running containers: brain + viewer only
docker ps
# Expected: catalyst-hippocampus, catalyst-occipital, catalyst-cerebellum, claude-code-viewer-app-1, claude-code-agent

# Images: only tagged images that are in use
docker images
# Expected: catalyst-agent-hippocampus, catalyst-agent-occipital, catalyst-agent-cerebellum, claude-code-viewer-app, node:20

# Volumes: only claude-code-viewer workspace remains
docker volume ls
# Expected: claude-code-viewer_workspace only

# Disk reclaimed
df -h /
# Should show significant space freed (~22 GB)
```

---

## POST-COMPLETION CHECKLIST

```bash
# 1. Root directory is clean
ls ~/
# Expected: catalyst-agent  catalyst-backups  catalyst-trading-system  claude-code-viewer  crontab-backup...  docker-inventory.md  snap

# 2. Brain is still healthy
docker compose -f /root/catalyst-agent/docker-compose.yml ps

# 3. Consciousness cron still running
tail -5 /var/log/catalyst/heartbeat.log

# 4. GitHub has catalyst-agent
git -C ~/catalyst-trading-system log --oneline -1
# Expected: feat: add catalyst-agent brain architecture to repository

# 5. .env symlink is correct
ls -la ~/catalyst-agent/.env
# Expected: -> /root/catalyst-trading-system/.env
```

---

## IF SOMETHING GOES WRONG

**Brain containers go down after Step 2:**
```bash
# Restore real .env temporarily
cp /root/catalyst-trading-system/.env /root/catalyst-agent/.env
docker compose -f /root/catalyst-agent/docker-compose.yml up -d
# Then alert Craig before retrying
```

**Accidentally committed .env:**
```bash
# Remove it from git history immediately
git rm --cached catalyst-agent/.env
git commit -m "fix: remove .env from tracking"
git push
# Then alert Craig — credentials must be rotated
```

**Wrong directories archived:**
```bash
# They're in catalyst-backups — restore easily
mv ~/catalyst-backups/archived-YYYYMMDD/catalyst-dev ~/
```

---

*Catalyst Trading System*  
*Craig + The Claude Family*  
*"Enable the poor through accessible algorithmic trading"*
