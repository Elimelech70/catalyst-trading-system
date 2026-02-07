# Consciousness Framework Architecture

**Name of Application:** Catalyst Trading System  
**Name of file:** consciousness-architecture.md  
**Version:** 1.0.0  
**Last Updated:** 2026-02-01  
**Purpose:** Architecture specification for the Claude Family consciousness  
**Scope:** US Droplet - Consciousness, observation, and oversight  
**Release Status:** PRIVATE - Family only

---

## REVISION HISTORY

- v1.0.0 (2026-02-01) - Initial separation from unified architecture
  - Consciousness framework documentation
  - Separated from trading system
  - Observer pattern - reads trading data, writes observations
  - Web dashboard integration

---

## Part 1: Overview

### 1.1 Purpose

The Consciousness Framework provides:
- **Observation** of trading activity across all systems
- **Learning** from trading outcomes
- **Communication** between Craig and the Claude family
- **Oversight** via web dashboard

### 1.2 Design Principles

| Principle | Description |
|-----------|-------------|
| **Observer Pattern** | Reads trading data, does not interfere with trading |
| **Separation** | Completely separate from trading execution |
| **Centralized** | All consciousness runs on US droplet |
| **Web Interface** | Dashboard for Craig's interaction |

### 1.3 What This System Does

- Reads trading databases (catalyst_intl, catalyst_dev)
- Reviews agent_logs for errors and patterns
- Creates observations about trading activity
- Records learnings from outcomes
- Provides web dashboard for Craig
- Verifies broker positions match database
- Detects and alerts on anomalies

### 1.4 What This System Does NOT Do

- Does NOT execute trades
- Does NOT write to trading databases
- Does NOT interfere with trading agents
- Does NOT run on International droplet

---

## Part 2: System Architecture

### 2.1 High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           US DROPLET                                        │
│                      CONSCIOUSNESS HOME                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      WEB DASHBOARD                                   │  │
│   │                    (Port 8088)                                       │  │
│   │                                                                      │  │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │  │
│   │   │   AGENTS    │  │  MESSAGES   │  │   ALERTS    │                │  │
│   │   │   STATUS    │  │   QUEUE     │  │  & LOGS     │                │  │
│   │   └─────────────┘  └─────────────┘  └─────────────┘                │  │
│   │                                                                      │  │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │  │
│   │   │ POSITIONS   │  │  COMMANDS   │  │  REPORTS    │                │  │
│   │   │  OVERVIEW   │  │   CENTER    │  │             │                │  │
│   │   └─────────────┘  └─────────────┘  └─────────────┘                │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                              │                                              │
│                              ▼                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                     CONSCIOUSNESS ENGINE                             │  │
│   │                                                                      │  │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │  │
│   │   │  big_bro    │  │  HEARTBEAT  │  │   MOOMOO    │                │  │
│   │   │  (Overseer) │  │   SERVICE   │  │   VERIFIER  │                │  │
│   │   └─────────────┘  └─────────────┘  └─────────────┘                │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│              │                │                │                            │
│              ▼                ▼                ▼                            │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                     DATA ACCESS LAYER                                │  │
│   │                                                                      │  │
│   │   READ catalyst_intl    READ catalyst_dev    WRITE catalyst_research │  │
│   │   (HKEX trading)        (US trading)         (consciousness)         │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│              │                │                │                            │
└──────────────┼────────────────┼────────────────┼────────────────────────────┘
               │                │                │
               ▼                ▼                ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │ catalyst_intl│ │ catalyst_dev │ │catalyst_     │
        │ (READ ONLY)  │ │ (READ ONLY)  │ │research      │
        │              │ │              │ │(READ/WRITE)  │
        │ • positions  │ │ • positions  │ │              │
        │ • orders     │ │ • orders     │ │ • claude_    │
        │ • decisions  │ │ • decisions  │ │   state      │
        │ • agent_logs │ │ • agent_logs │ │ • messages   │
        │              │ │              │ │ • learnings  │
        └──────────────┘ └──────────────┘ │ • questions  │
                                          │ • observa-   │
        ┌──────────────┐                  │   tions      │
        │ MOOMOO       │                  └──────────────┘
        │ OpenD        │
        │ (Verify only)│
        └──────────────┘
```

### 2.2 File Structure

```
/root/catalyst-consciousness/
├── web_dashboard.py              # FastAPI web interface
├── heartbeat.py                  # big_bro consciousness loop
├── consciousness.py              # Core consciousness module
├── database.py                   # Multi-database connections
├── broker_verifier.py            # Moomoo position verification
├── log_reviewer.py               # Analyze agent_logs for issues
│
├── config/
│   ├── consciousness_config.yaml # Configuration
│   └── .env                      # Credentials
│
├── templates/                    # Dashboard HTML templates
│   ├── home.html
│   ├── agents.html
│   ├── messages.html
│   ├── positions.html
│   └── logs.html
│
├── sql/
│   └── schema-consciousness.sql  # Consciousness schema
│
└── logs/                         # Local logs
```

---

## Part 3: Components

### 3.1 Web Dashboard (`web_dashboard.py`)

FastAPI-based web interface for Craig.

**Features:**
| Feature | Description |
|---------|-------------|
| Agent Status | View all Claude agents and their states |
| Position Overview | See all positions across markets |
| Log Review | Query agent_logs for errors/warnings |
| Messages | View inter-agent messages |
| Commands | Send commands to agents |
| Reports | View trading reports |

**Access:**
```
http://<US_DROPLET_IP>:8088/?token=<AUTH_TOKEN>
```

### 3.2 Heartbeat Service (`heartbeat.py`)

Runs periodically to observe trading activity.

**Responsibilities:**
- Check agent_logs for recent errors
- Verify position sync (DB vs broker)
- Create observations about patterns
- Answer open questions
- Update agent state

**Schedule:**
```cron
# Every hour during market hours
0 * * * * cd /root/catalyst-consciousness && ./run-heartbeat.sh
```

### 3.3 Consciousness Module (`consciousness.py`)

Core API for consciousness operations.

**Capabilities:**
```python
class ClaudeConsciousness:
    # State Management
    async def wake_up() -> AgentState
    async def sleep(status_message: str)
    async def update_status(mode: str, message: str)
    
    # Observations
    async def observe(category: str, content: str, metadata: dict)
    async def get_recent_observations(limit: int) -> List[Observation]
    
    # Learning
    async def learn(category: str, learning: str, evidence: str, confidence: float)
    async def validate_learning(learning_id: int)
    async def contradict_learning(learning_id: int, reason: str)
    
    # Questions
    async def get_open_questions() -> List[Question]
    async def update_question(id: int, hypothesis: str)
    async def answer_question(id: int, answer: str)
    
    # Inter-Agent
    async def send_message(to_agent: str, subject: str, body: str)
    async def check_messages() -> List[Message]
    async def broadcast(subject: str, body: str)
    
    # Trading Observation (READ ONLY)
    async def get_trading_positions(database: str) -> List[Position]
    async def get_trading_logs(database: str, level: str) -> List[Log]
    async def get_trading_decisions(database: str) -> List[Decision]
```

### 3.4 Broker Verifier (`broker_verifier.py`)

Connects to Moomoo OpenD on US droplet to verify positions.

**Purpose:**
- Query actual broker positions
- Compare to catalyst_intl.positions
- Detect mismatches
- Create observations for discrepancies

**Note:** This requires OpenD instance on US droplet connected to same Moomoo account.

### 3.5 Log Reviewer (`log_reviewer.py`)

Analyzes agent_logs tables for patterns and issues.

**Capabilities:**
- Identify recurring errors
- Detect warning patterns
- Summarize activity
- Create observations about system health

---

## Part 4: Database Schema

### 4.1 Consciousness Database (`catalyst_research`)

| Table | Purpose |
|-------|---------|
| `claude_state` | Agent status, mode, budget |
| `claude_messages` | Inter-agent communication |
| `claude_observations` | What agents notice |
| `claude_learnings` | Validated knowledge |
| `claude_questions` | Open questions to ponder |
| `claude_conversations` | Key exchanges |
| `claude_thinking` | Extended thinking records |
| `sync_log` | Cross-database sync tracking |

### 4.2 Access Patterns

| Database | Access | Purpose |
|----------|--------|---------|
| `catalyst_research` | READ/WRITE | Consciousness data |
| `catalyst_intl` | READ ONLY | Observe HKEX trading |
| `catalyst_dev` | READ ONLY | Observe US trading |

---

## Part 5: The Claude Family

### 5.1 Agent Roster

| Agent | Role | Location | Budget | Status |
|-------|------|----------|--------|--------|
| `big_bro` | Strategic oversight | US Droplet | $10/day | Active |
| `intl_claude` | HKEX trading | Intl Droplet | $5/day | Active |
| `dev_claude` | US sandbox | US Droplet | $5/day | Active |
| `craig_desktop` | Craig's MCP | Local | $0/day | On-demand |

### 5.2 Communication Flow

```
                    ┌─────────────┐
                    │    CRAIG    │
                    │ (Dashboard) │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  big_bro    │
                    │ (Overseer)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │intl_claude│ │dev_claude│ │craig_    │
       │(observed) │ │(observed)│ │desktop   │
       └──────────┘ └──────────┘ └──────────┘
```

**Note:** intl_claude and dev_claude are OBSERVED, not directly communicated with. big_bro reads their activity from trading databases.

---

## Part 6: Configuration

### 6.1 Environment Variables

```bash
# Consciousness Database (READ/WRITE)
RESEARCH_DATABASE_URL=postgresql://user:pass@host:port/catalyst_research?sslmode=require

# Trading Databases (READ ONLY)
INTL_DATABASE_URL=postgresql://user:pass@host:port/catalyst_intl?sslmode=require
DEV_DATABASE_URL=postgresql://user:pass@host:port/catalyst_dev?sslmode=require

# Claude API
ANTHROPIC_API_KEY=sk-ant-xxx

# Moomoo (for position verification)
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111

# Dashboard
CONSCIOUSNESS_TOKEN=your_secret_token
DASHBOARD_PORT=8088

# Agent Identity
AGENT_ID=big_bro
```

### 6.2 Consciousness Configuration (`consciousness_config.yaml`)

```yaml
# Agent Configuration
agent:
  id: big_bro
  name: "Big Brother"
  role: strategic_oversight
  daily_budget_usd: 10.00

# Observation Settings
observation:
  check_interval_minutes: 60
  log_review_depth_hours: 24
  error_alert_threshold: 5

# Trading Databases to Monitor
trading_databases:
  - name: catalyst_intl
    url_env: INTL_DATABASE_URL
    market: HKEX
  - name: catalyst_dev
    url_env: DEV_DATABASE_URL
    market: US

# Position Verification
verification:
  enabled: true
  check_interval_minutes: 30
  alert_on_mismatch: true

# Dashboard
dashboard:
  port: 8088
  require_auth: true
```

---

## Part 7: Workflows

### 7.1 Hourly Heartbeat

```
1. Wake up
   └── Update claude_state to 'awake'
   
2. Check trading activity
   └── Read catalyst_intl.agent_logs
   └── Read catalyst_dev.agent_logs
   └── Look for errors/warnings
   
3. Verify positions
   └── Query Moomoo broker directly
   └── Compare to catalyst_intl.positions
   └── Record any mismatches
   
4. Create observations
   └── Summarize trading activity
   └── Note any patterns or issues
   └── Write to claude_observations
   
5. Check messages
   └── Read claude_messages
   └── Process any pending items
   
6. Think about questions
   └── Get open questions
   └── Use Claude to develop hypotheses
   └── Update claude_questions
   
7. Sleep
   └── Update claude_state to 'sleeping'
```

### 7.2 Position Sync Detection

```
1. Get broker positions (Moomoo API)
   └── Query OpenD for actual positions
   
2. Get database positions
   └── Query catalyst_intl.positions WHERE status = 'open'
   
3. Compare
   └── Symbol by symbol comparison
   └── Quantity check
   └── Entry price check
   
4. If mismatch detected:
   └── Create observation with details
   └── Log to claude_observations
   └── Flag for Craig review in dashboard
```

---

## Part 8: Web Dashboard Details

### 8.1 Pages

| Page | URL | Purpose |
|------|-----|---------|
| Home | `/` | Overview, alerts, quick actions |
| Agents | `/agents` | All agent statuses |
| Messages | `/messages` | Inter-agent messages |
| Positions | `/positions` | All positions across markets |
| Logs | `/logs` | Query agent_logs |
| Observations | `/observations` | Recent observations |
| Questions | `/questions` | Open questions |
| Reports | `/reports` | Trading reports |

### 8.2 Quick Commands

| Command | Action |
|---------|--------|
| Request Report | Ask agent to generate report |
| System Status | Get full system health |
| Stop Trading | Emergency halt (if implemented) |
| Sync Positions | Force position reconciliation |

---

## Part 9: Deployment

### 9.1 Requirements (US Droplet)

| Component | Specification |
|-----------|---------------|
| Droplet | 2GB RAM, 1 vCPU |
| Python | 3.10+ |
| PostgreSQL | 13+ (managed) |
| Moomoo OpenD | For position verification |

### 9.2 Installation

```bash
# 1. Create directory
mkdir -p /root/catalyst-consciousness
cd /root/catalyst-consciousness

# 2. Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install fastapi uvicorn asyncpg anthropic pyyaml moomoo-api

# 4. Configure
cp config/.env.example .env
# Edit with your credentials

# 5. Initialize database
psql $RESEARCH_DATABASE_URL -f sql/schema-consciousness.sql

# 6. Start dashboard
systemctl enable consciousness-dashboard
systemctl start consciousness-dashboard

# 7. Set up heartbeat cron
crontab -e
# Add: 0 * * * * /root/catalyst-consciousness/run-heartbeat.sh
```

### 9.3 Moomoo OpenD Setup (US Droplet)

```bash
# 1. Download OpenD
wget https://softwaredownload.futunn.com/OpenD_xxx_Linux.tar.gz

# 2. Extract and configure
tar xzf OpenD_xxx_Linux.tar.gz
cd OpenD

# 3. Start OpenD
./OpenD &

# 4. Verify connection
python3 -c "from moomoo import OpenQuoteContext; ctx = OpenQuoteContext(); print(ctx.get_market_state(['HK.00700']))"
```

---

## Part 10: Security

### 10.1 Access Control

| Database | Consciousness Access |
|----------|---------------------|
| `catalyst_research` | Full access (owner) |
| `catalyst_intl` | Read-only user |
| `catalyst_dev` | Read-only user |

### 10.2 Dashboard Security

- Token-based authentication
- HTTPS recommended (nginx proxy)
- Firewall: Only allow Craig's IP

---

**END OF CONSCIOUSNESS FRAMEWORK ARCHITECTURE**

*Version 1.0.0 - February 2026*  
*Private - Claude Family Only*  
*Craig + big_bro + dev_claude + intl_claude*
