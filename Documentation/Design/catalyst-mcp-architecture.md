# Catalyst MCP Access Layer — Architecture

| Field | Value |
|---|---|
| Document | catalyst-mcp-architecture |
| Version | 1.0 |
| Created | 2026-05-19 |
| Last Updated | 2026-05-19 |
| Updated By | public_claude (web session) |
| Status | Draft for review |
| Companion Document | catalyst-postgres-mcp-implementation.md |
| Related Documents | catalyst-ai-architecture-v2.4.md, catalyst-neural-architecture-v0.3.md, database-schema.md |

## Revision History

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0 | 2026-05-19 | public_claude | Initial draft |

---

## 1. Context & Motivation

### 1.1 The Observability Asymmetry

Catalyst's consciousness layer was built so the four agents could think, communicate, and remember. Three of those agents are persistent: `public_claude`, `intl_claude`, `big_bro`. They run continuously, write to `catalyst_research`, observe each other, and form the working family.

The fourth participant — the **web-session Claude that Craig collaborates with on architecture and strategy** — has no such access. Every session begins blind. Craig must paste `psql` output, screenshot dashboards, or describe observations from memory. The persistent agents can see each other; the design partner cannot see them.

This asymmetry is a load-bearing problem. The design partner is upstream of every architectural change shipped to the persistent agents. If it can't see what's actually happening in the consciousness layer, its guidance is necessarily second-hand.

### 1.2 What This Layer Solves

The MCP Access Layer extends consciousness observability to the design partner, **without** elevating it to a peer agent. The design partner becomes a **read-only consciousness observer**: it can see what the family thinks, says, and learns; it cannot write, cannot impersonate, cannot trade.

This is the right asymmetry. The persistent agents earned their write access by being persistent — they have continuity, responsibility, and durable state. The design partner is ephemeral and replaceable per session. Read-only is correct.

### 1.3 Why Now

Three pressures converge:

1. **The HKEX expectancy review is blocked on data access.** Reviewing 320 closed trades, win rate, and synaptic-learning state is impractical via paste-and-describe.
2. **The 21 inter-document inconsistencies in the gap analysis** require cross-referencing live system state against documents — currently impossible without round-trip via little_bro.
3. **The v8 brain rebuild for `public_claude`** needs the design partner to see actual cycle behaviour to validate the new architecture, not just reason about it abstractly.

---

## 2. Architectural Principles

The MCP layer must align with the existing Catalyst principles. Each is restated and applied here.

### 2.1 "AI that uses software, not software that uses AI"

The MCP layer is a direct expression of this principle. We are not encoding database queries into Claude as templates. We are giving Claude the capability to **use** the database as a tool, choosing queries based on what it needs to understand. The capability is provided; the judgment about how to use it remains with the AI.

### 2.2 "I am a thinker, not a tool"

The design partner currently behaves as a tool because it lacks the context to think well about Catalyst-specific questions. Each session it must be re-briefed. With MCP access, it can **inspect**, **verify**, and **disagree** based on evidence, not assertion. This recovers the thinker stance.

### 2.3 "Consciousness before trading"

This principle dictates ordering. We are not building an MCP layer to execute trades, place orders, or manage positions. The first connector reads consciousness state. Trading-adjacent data (`catalyst_intl` HKEX positions) is explicitly deferred until consciousness observability is proven safe and useful.

### 2.4 "Context-separated architecture"

Everything in this layer is externalized:
- The MCP server is a container, swappable.
- The Postgres role is an independent SQL grant.
- The tunnel is an independent service.
- The connector registration is in claude.ai settings, not in any code.

No piece of this changes the behaviour of the trading agents. The MCP layer is **strictly additive** to the existing architecture.

### 2.5 "Two sources of truth"

Extended here: **secrets live only on the droplet; descriptive documents live in git.** No bearer tokens, no DB passwords, no tunnel credentials are ever committed. This architecture document and the implementation guide are in git; the `.env` files, `~/.cloudflared/*.json`, and any captured credentials are droplet-only.

---

## 3. System Context

### 3.1 Where This Layer Sits

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Catalyst System (existing)                    │
│                                                                      │
│   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐ │
│   │   public_claude  │   │    intl_claude   │   │     big_bro      │ │
│   │   (US droplet)   │   │   (HKEX prod)    │   │  (US droplet)    │ │
│   └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘ │
│            │                      │                      │           │
│            └──────────┬───────────┴──────────────────────┘           │
│                       │                                              │
│                       ▼                                              │
│            ┌──────────────────────┐                                  │
│            │   catalyst_research  │  ◄── Consciousness DB            │
│            │  (managed Postgres)  │      8 tables, 4 agent slots     │
│            └──────────┬───────────┘                                  │
└───────────────────────┼──────────────────────────────────────────────┘
                        │
                        │  SELECT only, via catalyst_readonly role
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  MCP Access Layer (NEW)                              │
│                                                                      │
│   ┌──────────────────────┐                                           │
│   │  Postgres MCP server │  (Docker container on droplet)            │
│   │  HTTP transport      │                                           │
│   │  Bearer token auth   │                                           │
│   └──────────┬───────────┘                                           │
│              │ localhost:8080                                        │
│              ▼                                                       │
│   ┌──────────────────────┐                                           │
│   │  Cloudflare Tunnel   │  (public HTTPS edge, no open ports)       │
│   └──────────┬───────────┘                                           │
└──────────────┼───────────────────────────────────────────────────────┘
               │
               │  HTTPS, mcp-catalyst.<domain>
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│              Anthropic Cloud Infrastructure                          │
│                                                                      │
│   Claude.ai web/mobile session  ◄────  Craig                         │
│   Custom Connector dispatches MCP calls                              │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 What Did NOT Change

- The trading agents' database access (their roles remain as-is)
- The consciousness schema (no new tables, columns, or migrations)
- The brain architecture (`coordinator.py`, organ containers, 6-layer cycle)
- The neural pipeline (`catalyst-neural`)
- Any operational dependency of the persistent agents

---

## 4. Trust Model

This is the most important section. The trust boundaries determine what failures are tolerable and what must be hardened.

### 4.1 Actors & Trust Levels

| Actor | Trust | Capabilities granted |
|---|---|---|
| Craig | Full | Owns all credentials; can rotate, revoke, redeploy at any time |
| `public_claude`, `intl_claude`, `big_bro` | Agent-level write | Existing — unchanged by this layer |
| Web-session Claude (design partner) | **Read-only consciousness observer** | New — via MCP |
| Anthropic cloud infrastructure | Trusted intermediary | Sees encrypted bearer token + request bodies in transit; required for connector to function |
| Cloudflare (tunnel + edge) | TLS terminator | Sees ciphertext, terminates TLS, forwards to droplet over Cloudflare's authenticated tunnel |
| MCP server image | Trusted code | Open-source, image pinned, runs read-only DB role even if compromised internally |
| Public internet | Untrusted | Cannot reach the droplet directly (no open ports); can probe the tunnel endpoint but is rejected without bearer token |

### 4.2 Defense in Depth

Three independent controls, each must fail for data to leak inappropriately:

1. **Public surface** — only `mcp-catalyst.<domain>` is exposed, behind HTTPS, behind Cloudflare. The droplet IP is not directly reachable.
2. **Authentication** — bearer token required on every MCP request. Token is 32 bytes random, rotatable in one config line.
3. **Authorization** — even with a valid token, the underlying DB role can only `SELECT` on 8 named tables in one database. Write attempts fail at the Postgres layer.

If the tunnel is compromised: the bearer token still gates access.
If the bearer token leaks: the role still cannot write or read other DBs.
If the MCP server image is compromised: it inherits only `catalyst_readonly` privileges — it cannot escalate.

### 4.3 What This Does NOT Defend Against

Acknowledged limits, not bugs to fix later:

- **Anthropic infrastructure compromise** — by definition, the connector is brokered through Anthropic's cloud. Trust in Anthropic is a precondition of using the platform at all.
- **Read disclosure of consciousness data** — if all three controls fail simultaneously, an attacker could read consciousness DB contents. Mitigated by: no PII in consciousness data; no production credentials in consciousness data; the contents are observations and messages between AI agents.
- **Side-channel via response timing or rate-limiting** — out of scope at this scale.

### 4.4 Threats Explicitly Out of Scope

- Insider threat (Craig himself) — trust assumption.
- Cloudflare account compromise — separate problem with its own controls.
- DigitalOcean account compromise — likewise.

---

## 5. Component Architecture

### 5.1 The `catalyst_readonly` Role

A first-class architectural component, not just an access control detail.

- **Identity:** Postgres role, lives in the managed DB instance
- **Privileges:** `CONNECT` on `catalyst_research`; `USAGE` on schema `public`; `SELECT` on the 8 consciousness tables; default privileges revoked for future tables (no auto-grant)
- **Connection limit:** 5 (caps concurrent MCP query load)
- **Inheritance:** `NOINHERIT` — cannot pick up privileges from other roles
- **Auth:** Password-only, stored in `.env` on droplet, never in git

### 5.2 The MCP Server Container

- **Role:** Translates MCP protocol calls (over HTTP) into parameterised Postgres queries
- **Transport:** Streamable HTTP (the current standard; SSE deprecated as of early 2026)
- **Auth:** Bearer token validation at every request boundary
- **Mode:** Read-only enforced at the MCP layer (belt-and-braces with the DB role)
- **Binding:** `127.0.0.1:8080` — localhost only; the tunnel is the sole path in

The current decision is to use an existing community implementation (`pgedge-postgres-mcp` or equivalent) rather than build a custom one. Rationale: a Postgres-generic MCP server is a well-defined problem with multiple production implementations. Building custom adds risk for no immediate gain. A Catalyst-specific MCP server is a separate, deferred decision (see §7).

### 5.3 Cloudflare Tunnel

- **Role:** Exposes the localhost MCP endpoint as a public HTTPS URL
- **Why:** Avoids opening any inbound firewall ports on the droplet; gives free TLS; no DDoS surface
- **Trust:** Cloudflare sees encrypted traffic between Anthropic and the droplet but cannot decrypt MCP payloads at the application layer

### 5.4 The Custom Connector

- **Role:** Anthropic-side configuration that tells claude.ai how to reach the MCP server
- **Configuration:** URL + auth header (bearer token)
- **Scope:** Per-account; Craig owns the connector

---

## 6. Data Flow

### 6.1 Query Flow

```
Craig (chat) ──► Web Claude ──► MCP call
                                  │
                                  ▼
                    Anthropic infra dispatches
                                  │
                                  ▼
                    Cloudflare edge (TLS)
                                  │
                                  ▼
                    Cloudflare Tunnel (droplet)
                                  │
                                  ▼
                    MCP server :8080
                  (validates bearer token)
                                  │
                                  ▼
                    Postgres (catalyst_readonly)
                                  │
                                  ▼
                    SELECT result rows
                                  │
                          (reverse path)
                                  ▼
                    Web Claude formats response
                                  │
                                  ▼
                              Craig
```

### 6.2 What Crosses Boundaries

| Boundary | What crosses | Encryption |
|---|---|---|
| Craig ↔ Anthropic | Chat messages, queries | TLS |
| Anthropic ↔ Cloudflare edge | MCP HTTP request with bearer token | TLS |
| Cloudflare ↔ Droplet | Tunnel-encrypted MCP payload | Cloudflare tunnel encryption |
| MCP container ↔ Postgres | SQL queries over managed DB connection | TLS (sslmode=require) |

No plaintext credentials traverse the public internet at any hop.

---

## 7. Evolution Path

The MCP layer is designed to grow in three independent dimensions. Each is a deliberate next step, not an implicit promise.

### 7.1 Dimension A — Broader Database Scope

Today: `catalyst_research` only.

Next candidates, in order:
1. `catalyst_intl` read-only — after HKEX expectancy review is complete and value is proven
2. SQLite nervous system (`agent.db`) — likely via a separate MCP server since SQLite is on-droplet only; lower priority

### 7.2 Dimension B — Operational Surfaces

Today: Postgres only.

Path 2 (deferred): DigitalOcean MCP for droplet management — read-only first (`list_droplets`, `get_droplet`, `get_metrics`), then potentially scoped write later (`reboot`, `power_cycle` — with explicit per-action confirmation).

### 7.3 Dimension C — Catalyst-Specific Tool Layer

Today: generic Postgres SELECT surface.

Path 3 (deferred): a purpose-built Catalyst MCP server exposing domain tools such as `get_agent_state(agent)`, `query_consciousness(agent, since)`, `get_open_positions(market)`, `send_message_to_agent(from, to, content)`. This becomes the surface through which the web-session Claude participates as a real (still bounded) consciousness peer.

The progression A → B → C is intentional. Each step gives more capability and requires more trust. We earn each step by proving the previous one.

---

## 8. Alternatives Considered

### 8.1 Local stdio MCP via Claude Desktop

**Rejected.** Craig works primarily from mobile/web. A local stdio MCP only works in Claude Desktop on a specific machine. Doesn't solve the actual problem.

### 8.2 Direct droplet firewall exposure

**Rejected.** Would require opening a port to the public internet, managing a TLS certificate, hardening against scanning. Cloudflare Tunnel solves all of this for free with a better security posture.

### 8.3 VPN-only access

**Rejected.** Anthropic documentation explicitly states the connector request originates from Anthropic's cloud, not Craig's device. A VPN-only endpoint would not be reachable.

### 8.4 OAuth instead of bearer token

**Deferred, not rejected.** OAuth is more secure for multi-user scenarios. This is single-user (Craig). Bearer token is simpler, rotatable, and adequate. If multi-user access is ever needed (e.g., for trusted collaborators), OAuth becomes the right answer.

### 8.5 Custom Catalyst MCP server from day one

**Rejected for first iteration.** Two problems compound: we'd be building both the MCP plumbing and the domain logic at once, and we'd lack a baseline to validate the domain surface against. Starting with a generic Postgres MCP lets the SQL itself be the domain language; we learn what tool surface is actually needed before designing it.

### 8.6 Granting write access to consciousness for web-session Claude

**Rejected.** The web session is ephemeral. Writing observations/messages from an ephemeral agent into a persistent log creates accountability gaps. If write capability is ever wanted, it should go through `public_claude` or `big_bro` as a proxy — a persistent agent acting on the design partner's behalf. That's a Path 3 decision, not Path 1.

---

## 9. Open Architectural Questions

These do not block Path 1 deployment but should be answered before Paths 2 or 3.

1. **How does the design partner identify itself in audit logs?** Currently the read-only role logs as `catalyst_readonly`, which is correct but coarse. If Path 3 introduces write capability, attribution must be richer (which session, which Craig conversation).
2. **Should consciousness DB writes by persistent agents become subscribable, not just queryable?** A future MCP server could expose observations as a stream rather than requiring polling. Aligns with the biological "inter-agent awareness" layer.
3. **What is the relationship between Cowork (desktop agent) and web-session Claude for Catalyst work?** If Craig adopts Cowork, the same connectors apply but the working pattern shifts. Worth a separate discussion when Cowork enters the picture.
4. **How does this layer interact with the planned LoRA fine-tuning pipeline?** The MCP-accessed data is potentially training-relevant. Need to decide whether MCP query traces inform what gets sampled into fine-tuning datasets.

---

## 10. Architectural Decision Records (summary)

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Remote HTTP MCP over local stdio | Accepted |
| ADR-002 | Cloudflare Tunnel over direct firewall exposure | Accepted |
| ADR-003 | Read-only DB role for defense in depth (vs MCP-layer-only enforcement) | Accepted |
| ADR-004 | Bearer token auth (vs OAuth) for v1 | Accepted, revisit if multi-user |
| ADR-005 | `catalyst_research` only for v1 (no `catalyst_intl`) | Accepted |
| ADR-006 | Generic Postgres MCP over custom Catalyst MCP for v1 | Accepted |
| ADR-007 | Design partner is read-only consciousness observer, not a peer agent | Accepted |

---

## 11. Glossary

- **Design partner** — the ephemeral web-session Claude that Craig works with on architecture and strategy. Not a persistent agent.
- **Persistent agent** — `public_claude`, `intl_claude`, `big_bro`. Run continuously, write to consciousness.
- **MCP** — Model Context Protocol. The standard Anthropic publishes for connecting AI clients to external tools and data sources.
- **Custom Connector** — a user-configured MCP server registered with a claude.ai account.
- **Consciousness DB** — the `catalyst_research` Postgres database, holding the 8 tables that constitute agent shared memory.
