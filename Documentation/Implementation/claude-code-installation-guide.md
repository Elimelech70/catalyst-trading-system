# Claude Code & Claude Code Viewer — Installation Guide

**Droplet:** DigitalOcean (68.183.177.11)
**OS:** Ubuntu 22.04.5 LTS
**Date Installed:** 2 March 2026
**Last Updated:** 2 March 2026

---

## 1. Infrastructure Overview

```
                   Internet
                      │
              ┌───────┴───────┐
              │   UFW Firewall │
              └───────┬───────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
    Port 8080    Port 8081    Port 22
         │            │            │
  ┌──────┴──────┐ ┌───┴────┐  ┌───┴───┐
  │  Catalyst   │ │ Claude │  │  SSH  │
  │  Dashboard  │ │ Code   │  │       │
  │  (Nginx)    │ │ Viewer │  │       │
  └─────────────┘ │ (Nginx)│  └───────┘
                  └───┬────┘
                      │ proxy_pass
                      │
               ┌──────┴──────┐
               │   Docker    │
               │  Container  │
               │  Port 3400  │
               └──────┬──────┘
                      │ volumes
          ┌───────────┼───────────┐
          │           │           │
   ~/.claude     project dir   workspace
   (read-write)  (read-only)   (docker vol)
```

### Software Versions

| Component | Version |
|-----------|---------|
| Ubuntu | 22.04.5 LTS |
| Node.js | v20.19.5 |
| npm | 10.8.2 |
| Docker | 28.3.3 |
| Docker Compose | v2.39.1 |
| Nginx | 1.18.0 |
| Claude Code CLI | 2.1.63 |
| Claude Code Viewer | v0.6.0 |

### Network Ports

| Port | Service | Access |
|------|---------|--------|
| 22 | SSH | External |
| 80 | HTTP redirect | External |
| 443 | HTTPS (MCP) | External |
| 3400 | Claude Code Viewer (Docker internal) | Localhost only |
| 8080 | Catalyst Dashboard (Nginx) | External |
| 8081 | Claude Code Viewer (Nginx) | External |
| 5000-5009 | Catalyst microservices | Docker internal only |
| 6379 | Redis | Docker internal only |

---

## 2. Claude Code CLI

### Installation

Claude Code is installed via npm globally:

```bash
npm install -g @anthropic-ai/claude-code
```

### Binary Location

```
/root/.local/bin/claude  →  symlink to /root/.local/share/claude/versions/2.1.63
```

### Installed Versions (historical)

```
/root/.local/share/claude/versions/
├── 2.1.12
├── 2.1.34
├── 2.1.62
└── 2.1.63    ← current
```

### Update Command

```bash
npm update -g @anthropic-ai/claude-code
```

### Configuration Directory

```
/root/.claude/
├── .credentials.json          # API authentication credentials
├── history.jsonl              # Global session index
├── settings.json              # Global settings (currently empty {})
├── settings.local.json        # Local permission overrides
├── stats-cache.json           # Usage statistics cache
├── mcp-needs-auth-cache.json  # MCP auth cache
├── backups/                   # Configuration backups
├── cache/                     # General cache
├── debug/                     # Debug logs (written by SDK)
├── downloads/                 # Downloaded files
├── file-history/              # File change tracking
├── paste-cache/               # Clipboard paste cache
├── plans/                     # Plan mode files
├── plugins/                   # Installed plugins
├── projects/                  # Per-project session data
│   ├── -root-catalyst-trading-system/
│   │   ├── *.jsonl            # Session conversation logs
│   │   ├── */                 # Session working directories
│   │   ├── memory/            # Persistent auto-memory
│   │   └── sessions-index.json
│   └── -root-catalyst-trading-system-Documentation-Implementation/
├── session-env/               # Session environment snapshots
├── shell-snapshots/           # Shell state snapshots
├── statsig/                   # Feature flag data
├── telemetry/                 # Usage telemetry
└── todos/                     # Task tracking data
```

### Local Permissions (`/root/.claude/settings.local.json`)

```json
{
  "permissions": {
    "allow": [
      "Bash(PGPASSWORD='...' psql:*)",
      "Bash(docker logs:*)",
      "Bash(curl:*)",
      "Bash(docker inspect:*)",
      "Bash(python3:*)",
      "Bash(docker-compose build:*)",
      "Bash(docker-compose up:*)",
      "Bash(docker ps:*)"
    ],
    "deny": [],
    "ask": []
  }
}
```

### API Key

Stored in `/root/catalyst-trading-system/.env` as `ANTHROPIC_API_KEY`.

### Verification Commands

```bash
# Check version
claude --version

# Check binary path
which claude
ls -la $(which claude)

# Check authentication
claude "hello" --print   # quick test
```

---

## 3. Claude Code Viewer

### Source Repository

- **Upstream:** https://github.com/d-kimuson/claude-code-viewer
- **Local clone:** `/root/claude-code-viewer`
- **Version:** v0.6.0 (commit `21dd4db`)

### Directory Structure

```
/root/claude-code-viewer/
├── Dockerfile                 # Multi-stage build (modified — see below)
├── docker-compose.yml         # Production config (modified — see below)
├── package.json               # v0.6.0
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── src/
│   └── server/                # Backend (Hono framework)
│       ├── hono/
│       │   ├── routes/        # API routes
│       │   └── middleware/    # Auth middleware
│       └── core/              # Business logic
├── dist/                      # Built output (inside container)
├── scripts/
│   └── docker-entrypoint.sh
└── ...
```

### Docker Configuration

#### Dockerfile (`/root/claude-code-viewer/Dockerfile`)

Modified from upstream to fix build issues with `lefthook` requiring a git repository:

```dockerfile
# syntax=docker/dockerfile:1.7

FROM node:22-slim AS base
ENV PNPM_HOME=/usr/local/share/pnpm
ENV PATH=${PNPM_HOME}:${PATH}
RUN corepack enable pnpm && apt-get update && apt-get install -y git openssh-client && rm -rf /var/lib/apt/lists/*

FROM base AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN git init                          # <-- FIX: lefthook needs a git repo during install
RUN --mount=type=cache,id=pnpm-store,target=/root/.pnpm-store \
    pnpm install --frozen-lockfile

COPY . .
RUN chmod +x scripts/docker-entrypoint.sh
RUN --mount=type=cache,id=pnpm-store,target=/root/.pnpm-store \
    pnpm build && pnpm prune --prod --ignore-scripts   # <-- FIX: --ignore-scripts prevents
                                                        #     lefthook from failing after prune

FROM base AS runner
WORKDIR /app
ENV CCV_ENV=production \
    PORT=3400 \
    HOSTNAME=0.0.0.0 \
    PATH="/app/node_modules/.bin:${PATH}"
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh
COPY package.json pnpm-lock.yaml ./
EXPOSE 3400
ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
CMD ["node", "dist/main.js"]
```

**Build fixes applied (not in upstream):**
1. `RUN git init` before `pnpm install` — the `prepare` lifecycle script runs `lefthook install` which needs a git repository
2. `--ignore-scripts` on `pnpm prune --prod` — after pruning dev dependencies, the `prepare` script would fail because `lefthook` binary is removed

#### Docker Compose (`/root/claude-code-viewer/docker-compose.yml`)

```yaml
services:
  app:
    build: .
    environment:
      CCV_ENV: production
      PORT: 3400
      CCV_PASSWORD: "Claude is my bro!"
      ANTHROPIC_BASE_URL: "${ANTHROPIC_BASE_URL}"
      ANTHROPIC_API_KEY: "<key-from-env>"
      ANTHROPIC_AUTH_TOKEN: "${ANTHROPIC_AUTH_TOKEN}"
    ports:
      - "3400:3400"
    volumes:
      - /root/.claude:/root/.claude                              # Read-write: SDK writes debug/session data
      - /root/catalyst-trading-system:/root/catalyst-trading-system:ro  # Read-only: project files for viewer
      - workspace:/root/workspace
    restart: unless-stopped
    init: true

volumes:
  workspace:
```

**Volume mounts explained:**

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `/root/.claude` | `/root/.claude` | rw | Session history, debug logs, credentials. Must be read-write because Claude SDK writes debug logs and session data |
| `/root/catalyst-trading-system` | `/root/catalyst-trading-system` | ro | Project source code. Viewer uses this for file tree, git status, and diff views |
| Docker volume `workspace` | `/root/workspace` | rw | Viewer's internal workspace |

**Environment variables:**

| Variable | Purpose | Required |
|----------|---------|----------|
| `CCV_ENV` | Set to `production` | Yes |
| `PORT` | Internal listener port | Yes (3400) |
| `CCV_PASSWORD` | Login password for web UI | Yes (for remote access) |
| `ANTHROPIC_API_KEY` | API key for sending messages via viewer | Yes (for chat feature) |
| `ANTHROPIC_BASE_URL` | Custom API base URL | No |
| `ANTHROPIC_AUTH_TOKEN` | Alternative auth token | No |

### Nginx Reverse Proxy

#### Config File: `/etc/nginx/sites-available/claude-code-viewer`

```nginx
server {
    listen 8081;
    listen [::]:8081;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:3400;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (used by viewer for live updates)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_cache_bypass $http_upgrade;

        # Long timeouts for WebSocket connections
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
```

#### Symlink

```
/etc/nginx/sites-enabled/claude-code-viewer  →  /etc/nginx/sites-available/claude-code-viewer
```

### Firewall Rule

```
8081/tcp    ALLOW    Anywhere    # Claude Code Viewer
```

### All Nginx Sites (for reference)

```
/etc/nginx/sites-enabled/
├── catalyst-dashboard      # Port 8080 → Catalyst web dashboard
├── catalyst-mcp            # Port 443  → MCP endpoint (HTTPS + API key auth)
└── claude-code-viewer      # Port 8081 → Claude Code Viewer
```

---

## 4. Access URLs

| Service | URL | Authentication |
|---------|-----|----------------|
| Claude Code Viewer (local) | http://localhost:3400 | Password |
| Claude Code Viewer (remote) | http://68.183.177.11:8081 | Password |
| Catalyst Dashboard | http://68.183.177.11:8080 | None |

**Viewer password:** `Claude is my bro!`

---

## 5. What Claude Code Viewer Reads

The viewer accesses Claude Code data from these paths:

```
~/.claude/history.jsonl                              # Global session index
~/.claude/projects/<project>/<session-id>.jsonl      # Per-session conversation logs
~/.claude/projects/<project>/sessions-index.json     # Project session index
```

No data is sent externally. Everything stays on the droplet.

### Viewer Features

| Feature | Description |
|---------|-------------|
| Session browser | All conversations sorted by recency, grouped by project |
| Full-text search | Ctrl+K fuzzy search across all conversations |
| Start sessions | Launch new Claude Code sessions from the browser |
| Resume sessions | Continue previous sessions with full context |
| File upload | Images, PDFs, text files directly in chat |
| Git diff viewer | Review and commit changes from the web UI |
| Mobile responsive | Access from phone on local network |
| Notifications | Audio alert when a running session completes |

---

## 6. Management Commands

### Start / Stop / Restart

```bash
# Start viewer
cd /root/claude-code-viewer && docker compose up -d

# Stop viewer
cd /root/claude-code-viewer && docker compose down

# Restart viewer
cd /root/claude-code-viewer && docker compose restart

# Rebuild after changes
cd /root/claude-code-viewer && docker compose up --build -d
```

### View Logs

```bash
# Container logs
docker logs claude-code-viewer-app-1 --tail 50

# Follow logs
docker logs claude-code-viewer-app-1 -f
```

### Check Status

```bash
# Container status
docker ps --filter "name=claude-code-viewer"

# HTTP health check
curl -s -o /dev/null -w "%{http_code}" http://localhost:3400/

# Nginx status
systemctl status nginx
```

### Update Viewer

```bash
cd /root/claude-code-viewer
git pull origin main
docker compose up --build -d
```

### Update Claude Code CLI

```bash
npm update -g @anthropic-ai/claude-code
claude --version
```

### Change Password

Edit `/root/claude-code-viewer/docker-compose.yml`, update `CCV_PASSWORD`, then:

```bash
cd /root/claude-code-viewer && docker compose up -d
```

---

## 7. Troubleshooting

### Viewer shows "Unauthorized"
- Password not set or container needs restart after password change
- Fix: `cd /root/claude-code-viewer && docker compose up -d`

### 400 Bad Request when clicking a project
- Project directory not mounted in container
- Fix: Add project path to `volumes:` in docker-compose.yml and restart

### "Failed to send message"
- `ANTHROPIC_API_KEY` not set in docker-compose.yml, OR
- `~/.claude` mounted as read-only (SDK needs to write debug/session files)
- Fix: Ensure API key is set and `~/.claude` is mounted without `:ro`

### "EROFS: read-only file system"
- `~/.claude` is mounted as `:ro`
- Fix: Change volume mount to `/root/.claude:/root/.claude` (no `:ro` suffix)

### Container won't start
```bash
docker logs claude-code-viewer-app-1 --tail 50
docker compose down && docker compose up --build -d
```

### Nginx 502 Bad Gateway
- Container isn't running
- Fix: `cd /root/claude-code-viewer && docker compose up -d`

---

## 8. Build Issues & Fixes Applied

These fixes were applied to the upstream repository to make Docker builds work:

### Issue 1: `lefthook install` fails during `pnpm install`

**Error:** `fatal: not a git repository`
**Cause:** The `prepare` lifecycle script in `package.json` runs `lefthook install`, which requires a git repository. Docker build context has no `.git` directory.
**Fix:** Added `RUN git init` before `pnpm install` in the Dockerfile.

### Issue 2: `lefthook install` fails during `pnpm prune --prod`

**Error:** `sh: 1: lefthook: not found`
**Cause:** After `pnpm prune --prod` removes dev dependencies, the `prepare` script triggers again but `lefthook` binary was just pruned.
**Fix:** Added `--ignore-scripts` flag to the prune command.

---

## 9. File Inventory

### All files created or modified during installation

| File | Action | Purpose |
|------|--------|---------|
| `/root/claude-code-viewer/` | Created (git clone) | Viewer source code |
| `/root/claude-code-viewer/Dockerfile` | Modified | Fixed lefthook build issues |
| `/root/claude-code-viewer/docker-compose.yml` | Modified | Added volumes, password, API key |
| `/etc/nginx/sites-available/claude-code-viewer` | Created | Nginx reverse proxy config |
| `/etc/nginx/sites-enabled/claude-code-viewer` | Created (symlink) | Enable Nginx site |
| UFW rule for port 8081 | Created | Firewall access |
