# Catalyst Postgres MCP Server — Implementation Guide

| Field | Value |
|---|---|
| Document | catalyst-postgres-mcp-implementation |
| Version | 1.0 |
| Created | 2026-05-19 |
| Last Updated | 2026-05-19 |
| Updated By | public_claude (web session, drafted for little_bro execution) |
| Status | Ready for execution |
| Target | catalyst-trading-prod-01 (US droplet) |
| Scope | Read-only access to `catalyst_research` only |

## Revision History

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0 | 2026-05-19 | public_claude | Initial draft |

---

## 1. Goal & Scope

### 1.1 Goal

Enable Craig's claude.ai web/mobile session to directly query the `catalyst_research` consciousness database via a remote MCP server. This unlocks:

- Querying `claude_state`, `messages`, `observations`, `learnings`, `questions`, `conversations`, `thinking`, `sync_log` directly from chat
- Reviewing inter-agent communication and consciousness activity without Craig pasting `psql` output
- Cross-referencing observations across `public_claude`, `intl_claude`, and `big_bro`

### 1.2 Explicit Non-Goals (this phase)

- ❌ No access to `catalyst_intl` (HKEX production DB) — separate decision, separate connector
- ❌ No write access to any database
- ❌ No DigitalOcean droplet management (Path 2, deferred)
- ❌ No exposure of `catalyst_agent.db` SQLite nervous system
- ❌ No catalyst-specific tool surface yet (Path 3, deferred)

### 1.3 Architectural Constraint Reminder

Per claude.ai documentation: **the MCP server must be reachable over the public internet from Anthropic's IP ranges.** Anthropic's cloud infrastructure makes the request, not Craig's device. This rules out VPN-only or local-network-only deployments.

---

## 2. Architecture Overview

```
┌──────────────────────────┐       HTTPS         ┌──────────────────────┐
│   claude.ai (Craig)      │  ────────────────►  │  Cloudflare Tunnel   │
│   Custom Connector       │   Bearer token      │  (public HTTPS edge) │
└──────────────────────────┘                     └──────────┬───────────┘
                                                            │ encrypted tunnel
                                                            ▼
                                              ┌─────────────────────────┐
                                              │ catalyst-trading-prod-01│
                                              │                         │
                                              │  Docker: catalyst-mcp   │
                                              │  (Postgres MCP server)  │
                                              │  Port 8080 internal     │
                                              └───────────┬─────────────┘
                                                          │ private network
                                                          ▼
                                              ┌─────────────────────────┐
                                              │ DO Managed Postgres     │
                                              │ DB: catalyst_research   │
                                              │ Role: catalyst_readonly │
                                              └─────────────────────────┘
```

### 2.1 Component Choices & Rationale

- **Cloudflare Tunnel** — gives us a public HTTPS endpoint without opening firewall ports on the droplet. No IP exposure, automatic TLS, free tier covers this trivially.
- **Docker container** — fits the existing organ-container pattern on the droplet. Isolation, easy rollback (`docker stop`), no host pollution.
- **Bearer token auth at MCP layer** — simplest workable auth for a single-tenant setup. Token rotation is a one-line change.
- **Read-only Postgres role** — defense in depth. Even if the token leaks, the worst case is read disclosure of consciousness data, not modification of production state.

---

## 3. Pre-Flight Checks

Run all of these before starting. **STOP if any fail and report back.**

### 3.1 Environment Checks

```bash
# Confirm we're on the right droplet
hostname
# Expected: catalyst-trading-prod-01 (or whatever the hostname is)

# Confirm Docker is running
docker ps | head -3
# Expected: Docker daemon responding, organ containers listed

# Confirm we can reach the managed Postgres
psql "$DATABASE_URL" -c "SELECT current_database(), current_user, version();" | head -10
# Expected: returns catalyst_research (or current DB) + Postgres version

# Confirm cloudflared availability (will install if missing)
which cloudflared || echo "NOT INSTALLED — will install in Phase 3"

# Confirm we have outbound HTTPS
curl -s -o /dev/null -w "%{http_code}" https://api.cloudflare.com/client/v4/
# Expected: 200 or 401 (auth, but reachable)
```

### 3.2 Credential Checks

Before doing anything, confirm Craig has provided (or you have access to):

- [ ] Postgres admin connection string for the managed DB (to create the read-only role)
- [ ] Cloudflare account access (or Craig will run cloudflared login interactively)
- [ ] A domain name on Cloudflare (e.g. `mcp.catalyst.<craig-domain>` — Craig must confirm)

**STOP CONDITION:** If Craig has not confirmed a Cloudflare domain to use, halt here and ask. Do not attempt to provision DNS.

### 3.3 Git State Check

```bash
cd /root/catalyst-trading-system  # or wherever the repo is
git fetch origin
git status
# Expected: clean, on main, up-to-date with origin/main

# If drifted:
# git reset --hard origin/main
```

---

## 4. Phase 1 — Database Role Creation

### 4.1 Create the Read-Only Role

Connect as the admin user (the one with DATABASE_URL privileges):

```bash
psql "$DATABASE_URL_ADMIN" <<'SQL'
-- Generate a strong password first and capture it
\set readonly_password `openssl rand -base64 32`

CREATE ROLE catalyst_readonly WITH
  LOGIN
  PASSWORD :'readonly_password'
  CONNECTION LIMIT 5
  NOINHERIT
  NOCREATEDB
  NOCREATEROLE
  NOSUPERUSER;

-- Restrict to catalyst_research database only
REVOKE ALL ON DATABASE catalyst_research FROM catalyst_readonly;
GRANT CONNECT ON DATABASE catalyst_research TO catalyst_readonly;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO catalyst_readonly;

-- Grant SELECT only on the 8 consciousness tables
GRANT SELECT ON 
  claude_state,
  messages,
  observations,
  learnings,
  questions,
  conversations,
  thinking,
  sync_log
TO catalyst_readonly;

-- Future-proof: ensure newly added consciousness tables are not auto-granted
-- (explicit grants only)
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM catalyst_readonly;

-- Verify
\du catalyst_readonly
\dp claude_state
SQL
```

**Capture the generated password.** It will go into the Docker container's environment, not into any file checked into git.

### 4.2 Verify the Role

```bash
# Connect as the new role and confirm scope
PGPASSWORD='<generated_password>' psql \
  -h <db_host> -p <db_port> -U catalyst_readonly -d catalyst_research \
  -c "SELECT count(*) FROM observations LIMIT 1;"
# Expected: returns a count

# Verify write is blocked
PGPASSWORD='<generated_password>' psql \
  -h <db_host> -p <db_port> -U catalyst_readonly -d catalyst_research \
  -c "INSERT INTO observations (agent_name, content) VALUES ('test', 'should fail');"
# Expected: ERROR: permission denied for table observations

# Verify other databases are blocked
PGPASSWORD='<generated_password>' psql \
  -h <db_host> -p <db_port> -U catalyst_readonly -d catalyst_intl \
  -c "SELECT 1;"
# Expected: FATAL: permission denied for database "catalyst_intl"
```

**STOP CONDITION:** If write is NOT blocked or other DBs are NOT blocked, fix the role grants before proceeding.

---

## 5. Phase 2 — MCP Server Deployment

### 5.1 Choose & Pin the MCP Server Image

Two viable options. Pick **A** unless Craig prefers **B**.

**Option A (recommended): pgedge-postgres-mcp**

- Purpose-built remote Postgres MCP server
- Streamable HTTP transport (the current standard)
- Read-only transactions by default
- Token authentication built in

**Option B: Anthropic reference + mcp-remote proxy**

- Uses official `@modelcontextprotocol/server-postgres` (stdio)
- Wrap with `mcp-remote` to expose HTTP
- More moving parts but uses Anthropic's reference implementation

**Action for little_bro:** Before pulling either image, web-search the current state of `pgedge-postgres-mcp` (or the chosen alternative) to confirm:
- Latest stable image tag
- Current env var names for connection string and auth token
- Streamable HTTP transport is supported (not only stdio)

If the package landscape has shifted since this doc was written, **report findings and stop** before deploying. Don't substitute a different package without checking with Craig.

### 5.2 Generate the Bearer Token

```bash
# 32 bytes of randomness, base64 encoded
openssl rand -base64 32
# Capture output — this is MCP_AUTH_TOKEN
```

### 5.3 Create the Docker Compose Service

Add a new service to the existing Catalyst docker-compose, or create a separate compose file at `/root/catalyst-mcp/docker-compose.yml`:

```yaml
version: '3.8'

services:
  catalyst-mcp:
    image: <pinned-image-tag-from-5.1>
    container_name: catalyst-mcp
    restart: unless-stopped
    environment:
      DATABASE_URL: "postgresql://catalyst_readonly:${READONLY_DB_PASSWORD}@${DB_HOST}:${DB_PORT}/catalyst_research?sslmode=require"
      MCP_AUTH_TOKEN: "${MCP_AUTH_TOKEN}"
      MCP_READ_ONLY: "true"
      MCP_TRANSPORT: "http"
    ports:
      - "127.0.0.1:8080:8080"   # bind to localhost only — tunnel will reach it
    networks:
      - catalyst
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

networks:
  catalyst:
    external: true
```

### 5.4 Create the .env File

```bash
cat > /root/catalyst-mcp/.env <<EOF
READONLY_DB_PASSWORD=<password from 4.1>
DB_HOST=<managed postgres host>
DB_PORT=<managed postgres port, usually 25060 on DO>
MCP_AUTH_TOKEN=<token from 5.2>
EOF

chmod 600 /root/catalyst-mcp/.env
```

**Never commit .env to git.** Verify:

```bash
cd /root/catalyst-trading-system
grep -r "catalyst-mcp/.env" .gitignore || echo "ADD TO .gitignore"
```

### 5.5 Start the Container

```bash
cd /root/catalyst-mcp
docker compose up -d
docker compose logs --tail 50 catalyst-mcp
# Expected: server bound to 0.0.0.0:8080, accepting connections
```

### 5.6 Local Verification

```bash
# Should respond to MCP initialize
curl -s -X POST http://127.0.0.1:8080/mcp \
  -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"verify","version":"1.0"}}}'

# Expected: JSON response with serverInfo and capabilities
# Exact endpoint path may differ by image — check image docs
```

**STOP CONDITION:** If the server doesn't respond or rejects the token, debug here. Do NOT proceed to expose it publicly until local verification passes.

---

## 6. Phase 3 — Cloudflare Tunnel

### 6.1 Install cloudflared

```bash
# If not already installed
curl -L -o cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
cloudflared --version
```

### 6.2 Authenticate (Craig must do this interactively)

**This step requires Craig's involvement** — cloudflared will open a browser URL Craig has to click.

```bash
cloudflared tunnel login
# Outputs a URL — Craig opens it, picks the domain, authorizes
```

### 6.3 Create the Tunnel

```bash
cloudflared tunnel create catalyst-mcp
# Captures a tunnel UUID and credentials JSON at ~/.cloudflared/<UUID>.json
```

### 6.4 Configure Routing

Create `/root/.cloudflared/config.yml`:

```yaml
tunnel: <UUID from 6.3>
credentials-file: /root/.cloudflared/<UUID>.json

ingress:
  - hostname: mcp-catalyst.<craig-domain>
    service: http://127.0.0.1:8080
  - service: http_status:404
```

### 6.5 Create DNS Record

```bash
cloudflared tunnel route dns catalyst-mcp mcp-catalyst.<craig-domain>
```

### 6.6 Run as a Service

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
sudo systemctl status cloudflared
# Expected: active (running), tunnel connection established
```

### 6.7 Public Verification

```bash
# From any machine on the public internet (or just curl from the droplet)
curl -s -X POST https://mcp-catalyst.<craig-domain>/mcp \
  -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"verify","version":"1.0"}}}'

# Expected: same response as in 5.6, but over HTTPS via Cloudflare
```

**STOP CONDITION:** If public endpoint doesn't respond, check:
1. `systemctl status cloudflared` — tunnel running?
2. Cloudflare dashboard — tunnel showing as healthy?
3. DNS propagation — `dig mcp-catalyst.<craig-domain>` resolves?

---

## 7. Phase 4 — Add Custom Connector in claude.ai

**This step is Craig's, not little_bro's.** Document what Craig needs to do:

1. Go to claude.ai → Settings → Connectors
2. Click "Add custom connector"
3. Enter:
   - **Name:** `Catalyst Consciousness (research)`
   - **URL:** `https://mcp-catalyst.<craig-domain>/mcp` (exact path depends on the MCP image — check image docs)
   - **Advanced settings:** if the server uses OAuth, configure client ID/secret; if bearer token, the connector may need a header config (depends on Anthropic's connector UI at time of setup)
4. Save & enable

**STOP CONDITION:** If the connector UI requires OAuth and the image only supports bearer token, this becomes a wrapper problem — flag back to Craig before forcing a fix.

---

## 8. End-to-End Verification

In a new claude.ai conversation, Craig asks:

> "List the last 5 observations from intl_claude in the consciousness DB."

Expected behaviour:
- Claude calls the new MCP tool
- Returns a real result from the `observations` table

Other smoke tests:
- "What's the current state of public_claude?" → reads `claude_state`
- "Show me messages between big_bro and intl_claude from this week" → reads `messages`
- "Attempt to insert a test row into observations" → should be **rejected** (read-only enforcement)

---

## 9. Rollback Procedure

If anything goes wrong and we need to back out cleanly:

```bash
# 1. Stop the MCP container
cd /root/catalyst-mcp
docker compose down

# 2. Stop the tunnel
sudo systemctl stop cloudflared
sudo systemctl disable cloudflared

# 3. Remove the DNS record (in Cloudflare dashboard)

# 4. Drop the read-only role
psql "$DATABASE_URL_ADMIN" -c "DROP ROLE catalyst_readonly;"

# 5. Remove the connector in claude.ai (Craig does this)
```

No production trading systems are touched at any point. The `catalyst_readonly` role has no relationship to the roles used by `public_claude`, `intl_claude`, or `big_bro`.

---

## 10. Token & Credential Hygiene

After this session, the following must be rotated or are at risk:

| Item | Rotation Trigger |
|---|---|
| `catalyst_readonly` DB password | If shared in any chat or document |
| `MCP_AUTH_TOKEN` | If shared in any chat or document, OR every 90 days |
| Cloudflare API token (if used by little_bro non-interactively) | If shared or every 90 days |

Document where each lives:
- DB password: `/root/catalyst-mcp/.env` (chmod 600, droplet only)
- MCP token: same file
- Cloudflare credentials: `~/.cloudflared/<UUID>.json` (droplet only, never in git)

---

## 11. Open Questions for Craig

Before little_bro starts execution, Craig should confirm:

1. **Domain to use** — what's the Cloudflare-managed domain for the public hostname?
2. **MCP server image choice** — Option A (pgedge) or Option B (Anthropic reference + proxy)? (Recommend A.)
3. **DB host/port** — confirm the managed Postgres connection details
4. **Admin DB credential availability** — how does little_bro get `$DATABASE_URL_ADMIN` for Phase 1 without it being committed anywhere?
5. **Plan tier check** — Craig is on a paid claude.ai plan (Pro/Max), required for custom connectors? (Free tier limit is 1 custom connector.)

---

## 12. What Comes Next (deferred)

After this works and proves out:

- **Path 2:** DigitalOcean MCP for droplet management
- **Path 3:** Custom Catalyst MCP server with domain-specific tools (`get_agent_state`, `query_consciousness`, `send_message_to_agent`)
- **Extend Path 1:** add `catalyst_intl` connector after HKEX expectancy review and any required security review

---

## Appendix A — File Layout on the Droplet

```
/root/
├── catalyst-trading-system/      # git repo (existing)
├── catalyst-agent/                # droplet-only (existing)
├── catalyst-mcp/                  # NEW
│   ├── docker-compose.yml         # NOT in git
│   └── .env                       # NEVER in git, chmod 600
└── .cloudflared/                  # NEW
    ├── config.yml
    └── <UUID>.json                # tunnel credentials, NEVER in git
```

## Appendix B — .gitignore additions

Add to `catalyst-trading-system/.gitignore` (defense in depth, even though these dirs live outside the repo):

```
catalyst-mcp/
.cloudflared/
*.env
```
