# Claude Code Viewer — Ubuntu Setup Guide

**For:** Craig's Ubuntu laptop
**Date:** 2 March 2026
**Repo:** https://github.com/d-kimuson/claude-code-viewer

---

## Prerequisites

- Node.js >= 20.19.0
- Claude Code CLI installed and authenticated
- pnpm (optional but recommended)

### Check Node version

```bash
node --version
# Needs to be >= 20.19.0
# If not: nvm install 20 && nvm use 20
```

### Check Claude Code is working

```bash
claude --version
```

---

## Option A: Quick Start (npx — no install)

Fastest way to try it:

```bash
PORT=3400 npx @kimuson/claude-code-viewer@latest
```

Opens at `http://localhost:3400`. Done.

---

## Option B: Global Install

```bash
npm install -g @kimuson/claude-code-viewer
claude-code-viewer
```

Then open `http://localhost:3400`.

---

## Option C: Docker (fits your existing stack)

This is probably the best fit given your Docker workflow with Catalyst.

```bash
# Clone the repo
git clone https://github.com/d-kimuson/claude-code-viewer.git
cd claude-code-viewer

# Docker Compose (simplest)
docker compose up --build
```

Or build and run manually:

```bash
docker build -t claude-code-viewer .

docker run --rm -p 3400:3400 \
  -v ~/.claude:/root/.claude \
  claude-code-viewer
```

**Important:** The `-v ~/.claude:/root/.claude` mount gives the container access to your Claude Code conversation history. Without it, the viewer has no data to display.

---

## Option D: Development Mode (if you want to hack on it)

```bash
git clone https://github.com/d-kimuson/claude-code-viewer.git
cd claude-code-viewer
pnpm install
pnpm dev
```

---

## What It Reads

Claude Code Viewer reads from:

- `~/.claude/history.jsonl` — global session index
- `~/.claude/projects/<project>/<session-id>.jsonl` — per-project conversation logs

No external data is sent anywhere. Everything stays local.

---

## Key Features Once Running

| Feature | What it does |
|---|---|
| **Session browser** | All conversations, sorted by recency, grouped by project |
| **Full-text search** | Ctrl+K — fuzzy search across all conversations |
| **Start sessions** | Launch Claude Code sessions from the browser |
| **Resume sessions** | Pick up where you left off, with full context |
| **File upload** | Images, PDFs, text files directly in chat |
| **Git diff viewer** | Review and commit changes from the web UI |
| **Mobile responsive** | Access from your phone on local network |
| **Notifications** | Audio alert when a running session completes |

---

## Access From Phone / Other Devices

To access from your phone (e.g. while at the Sunday kitchen):

```bash
# Bind to all interfaces instead of just localhost
PORT=3400 npx @kimuson/claude-code-viewer@latest
```

Then access via `http://<your-laptop-ip>:3400` from your phone.

**Security note:** No authentication is built in. Only run on trusted networks, or put it behind a reverse proxy with auth if you want remote access.

---

## Run as a Systemd Service (optional)

If you want it always running alongside your Catalyst stack:

```bash
sudo tee /etc/systemd/system/claude-code-viewer.service << 'EOF'
[Unit]
Description=Claude Code Viewer
After=network.target

[Service]
Type=simple
User=craig
Environment=PORT=3400
ExecStart=/usr/bin/npx @kimuson/claude-code-viewer@latest
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable claude-code-viewer
sudo systemctl start claude-code-viewer
```

---

## Next Step

Once running, browse to `http://localhost:3400` and you'll see all your Claude Code sessions organised by project. Use Ctrl+K to search across everything.

This gives you the continuity layer to reference previous architecture conversations, implementation decisions, and design evolution — all searchable from a web browser.
