# Catalyst Trading System

> *Enable the poor through accessible algorithmic trading.*

An autonomous algorithmic trading platform built on a brain-and-organs AI agent architecture. The system learns to trade rather than executing coded logic, with neuroscience-inspired learning (Hebbian / LTP / LTD), inter-agent signal buses, and explicit consciousness layers.

For orientation, start with [`CLAUDE.md`](./CLAUDE.md).

---

## Architecture

The system is built around the **AI Agent Architecture** (general pattern) and the **Catalyst AI Architecture** (Catalyst-specific application). Both are versioned and live in [`Documentation/Design/`](./Documentation/Design/).

> Source-of-truth rule: folder path identifies the family, filename suffix identifies the version, highest version is current.

| Document family | Latest |
|---|---|
| `ai-agent-architecture-vX.md` | v8 |
| `catalyst-ai-architecture-vX.X.md` | v2.4 |
| `catalyst-neural-architecture-vX.X.md` | v0.3 |

---

## Code implementations

The repo contains four code implementations of the architecture. Each is independent — separate folder, separate lifecycle, separate `CLAUDE.md`.

| # | Implementation | Folder | Host | Status |
|---|---|---|---|---|
| 1 | **catalyst-agent** | [`catalyst-agent/`](./catalyst-agent/) | US droplet | Shelved (2026-05-18) |
| 2 | **catalyst-international** | [`catalyst-international/`](./catalyst-international/) | Intl droplet (SYD1, HKT) | Running — HKEX paper trading |
| 3 | **catalyst-neural** | [`catalyst-neural/`](./catalyst-neural/) | Laptop (RTX 4050) | Running — ML training → ONNX deploys to droplets |
| 4 | **catalyst-research** | (to be created) | US droplet | Planned |

Each running implementation is a **brain** (Claude AI as decision engine inside a coordinator script) plus **organs** (Python services that scan, execute, and monitor). The brain runs a six-layer consciousness cycle: Heartbeat → State → Self-Regulation → Working Memory → Inter-Agent → Voice, with the Decision Engine (Claude AI) called only after the firmware layers pass.

---

## Infrastructure

### Droplets

| Droplet | Role | Region | Specs | IP |
|---|---|---|---|---|
| `catalyst-trading-prod-01` | US | SGP1 / Ubuntu 22.04 | 4 GB / 80 GB | 68.183.177.11 |
| `catalyst-trading-system-international` | International (HKEX, AWST/HKT) | SYD1 / Ubuntu 24.04 | 4 GB / 50 GB | 209.38.87.27 |

### Databases (DigitalOcean managed PostgreSQL)

| Database | Used by |
|---|---|
| `catalyst_intl` | catalyst-international (HKEX trading) |
| `catalyst_research` | consciousness data; future home of catalyst-research |
| `catalyst_dev` | legacy US sandbox data (agent shelved) |

Schema reference: [`Documentation/Design/database-schema.md`](./Documentation/Design/database-schema.md)

### Brokers

| Implementation | Broker | Market | Mode |
|---|---|---|---|
| catalyst-international | Moomoo / OpenD | HKEX | Paper trading |
| catalyst-agent (shelved) | Alpaca | NYSE / NASDAQ | Paper trading |

---

## Quick start

### Read first

1. [`CLAUDE.md`](./CLAUDE.md) — root orientation
2. The `CLAUDE.md` inside whichever implementation folder you're working in
3. The latest version of `Documentation/Design/catalyst-ai-architecture-vX.X.md`

### Run an implementation

Each implementation has its own setup. See:

- catalyst-international: [`catalyst-international/CLAUDE.md`](./catalyst-international/CLAUDE.md) and `catalyst-international/docker-compose.yml`
- catalyst-agent: [`catalyst-agent/CLAUDE.md`](./catalyst-agent/CLAUDE.md) (currently shelved)
- catalyst-neural: [`catalyst-neural/README.md`](./catalyst-neural/README.md) (runs on laptop via systemd)

### Environment

```bash
cp .env.template .env
# Edit .env with credentials (Anthropic, broker, database URLs)
```

---

## Repository layout

```
catalyst-trading-system/
├── CLAUDE.md                  ← orientation (read first)
├── README.md                  ← this file
├── .env.template
│
├── catalyst-agent/            ← Implementation 1 (US, shelved)
├── catalyst-international/    ← Implementation 2 (HKEX, running)
├── catalyst-neural/           ← Implementation 3 (laptop, running)
│   (catalyst-research/)       ← Implementation 4 (planned)
│
├── Documentation/             ← authoritative for designs, configs, guides, reports
│   ├── Analysis/
│   ├── Configuration/
│   ├── Design/                ← architecture docs (versioned, highest = current)
│   ├── Implementation/
│   └── Reports/
│
├── services/
│   ├── consciousness/         ← heartbeat / dashboard (shelved)
│   └── shared/common/         ← shared modules
│
└── scripts/
```

---

## Status snapshot (2026-05-18)

| Host | What's running |
|---|---|
| Intl droplet (SYD1) | catalyst-international — coordinator + scanner + executor + monitor (Docker, MCP) |
| Laptop | catalyst-neural — collection daemon + weekly training pipeline |
| US droplet (SGP1) | nothing on application code; awaiting catalyst-research build |

---

## License

Proprietary — all rights reserved.

---

*Craig + Claude — The Catalyst Family*
*2026-05-18*
