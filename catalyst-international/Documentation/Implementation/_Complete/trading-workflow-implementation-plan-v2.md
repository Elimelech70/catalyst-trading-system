# TRADING WORKFLOW IMPROVEMENT - IMPLEMENTATION PLAN v2

**Name of Application:** Catalyst Trading System  
**Name of file:** trading-workflow-implementation-plan-v2.md  
**Version:** 2.0.0  
**Last Updated:** 2026-01-24  
**Purpose:** Implementation plan with context-separated architecture

---

## ARCHITECTURAL CHANGE: CONTEXT SEPARATION

### The Principle

**Tools should be dumb executors. Context should be external and editable.**

### Before vs After

```
BEFORE (Context Embedded in Tool)
─────────────────────────────────
news.py
├── POSITIVE_WORDS = {...}     ← Hardcoded
├── NEGATIVE_WORDS = {...}     ← Hardcoded  
├── STOCK_NAMES = {...}        ← Hardcoded
└── def get_news()             ← Logic

Problems:
- Change keywords = edit Python code
- Restart required for any change
- Can't version context separately
- Agent can't update own context


AFTER (Context Separated from Tool)
───────────────────────────────────
config/
└── news_context.yaml          ← Editable YAML
    ├── positive_keywords
    ├── negative_keywords
    ├── catalyst_types
    ├── sectors
    ├── stock_names
    └── thresholds

data/
└── news.py                    ← Pure logic
    └── def get_news()         ← Loads from config

Benefits:
- Change keywords = edit YAML
- Hot-reload possible (no restart)
- Version context separately from code
- Agent could update own context (future)
```

### Knowledge Layer Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                 AGENT KNOWLEDGE LAYERS                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  CODE (news.py, tools.py)        ← Fixed, never self-edit  │
│  ───────────────────────────                                │
│  CONTEXT (news_context.yaml)     ← Editable, hot-reload    │
│  ───────────────────────────                                │
│  MEMORY (consciousness DB)       ← Learning, always grows  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## FILES CREATED

### 1. config/news_context.yaml (Context)

**Location:** `/root/catalyst-international/config/news_context.yaml`  
**Size:** ~350 lines  
**Purpose:** All editable context for news sentiment analysis

**Contents:**
```yaml
version: "1.0.0"

positive_keywords:      # 80+ words (was 30)
negative_keywords:      # 30 words
catalyst_types:         # 5 tiers with multipliers
sectors:               # 7 HKEX sector groupings
stock_names:           # Symbol → company name mapping
thresholds:            # Sentiment thresholds
composite_weights:     # Scoring weights
```

**Key Additions from Gap Analysis:**
| Category | New Keywords | Addresses |
|----------|--------------|-----------|
| Corporate Actions | buyback, ipo, debut, spinoff | Pop Mart, MiniMax misses |
| Binary Events | approved, extension, reprieve | China Vanke miss |
| Policy | subsidy, stimulus, incentive | Li Auto miss |
| Business Metrics | users, milestone, deliveries | Ant Afu miss |

### 2. data/news.py (Tool)

**Location:** `/root/catalyst-international/data/news.py`  
**Size:** ~550 lines  
**Purpose:** News fetching and sentiment analysis (pure logic)

**Key Classes:**
| Class | Purpose |
|-------|---------|
| `NewsContext` | Loads config from YAML, supports hot-reload |
| `CatalystClassifier` | Classifies headlines into 5 tiers |
| `SectorTracker` | Detects sector-wide momentum |
| `NewsClient` | Main API - fetches news, calculates sentiment |

**Key Methods:**
| Method | Purpose |
|--------|---------|
| `get_context()` | Get/create context singleton |
| `reload_context()` | Hot-reload config without restart |
| `get_news(symbol)` | Fetch news with sentiment |
| `get_news_with_catalyst(symbol)` | News + catalyst classification |
| `has_catalyst(symbol)` | Quick check for positive catalyst |
| `check_sector_momentum(symbol)` | Detect sympathy plays |

---

## DEPLOYMENT GUIDE

### Phase 1: Deploy Files (30 minutes)

```bash
# SSH to international droplet
ssh root@209.38.87.27

# Navigate to project
cd /root/catalyst-international

# Backup existing news.py
cp data/news.py data/news.py.bak.$(date +%Y%m%d)

# Create config directory if needed
mkdir -p config

# Deploy new files (copy from local or paste)
# Option A: SCP from local machine
scp config/news_context.yaml root@209.38.87.27:/root/catalyst-international/config/
scp data/news.py root@209.38.87.27:/root/catalyst-international/data/

# Option B: Create files directly on server
nano config/news_context.yaml  # Paste content
nano data/news.py              # Paste content
```

### Phase 2: Install Dependencies (5 minutes)

```bash
# Activate virtual environment
source venv/bin/activate

# Install PyYAML if not present
pip install pyyaml

# Verify
python3 -c "import yaml; print('PyYAML OK')"
```

### Phase 3: Test (15 minutes)

```bash
# Test context loading
python3 -c "
from data.news import get_context
ctx = get_context()
print(f'Context version: {ctx.version}')
print(f'Positive keywords: {len(ctx.positive_keywords)}')
print(f'Catalyst types: {list(ctx.catalyst_types.keys())}')
"

# Test sentiment analysis
python3 -c "
from data.news import NewsClient

client = NewsClient()

tests = [
    'Pop Mart announces HK\$251M share buyback',
    'MiniMax IPO debuts on HKEX',
    'Vanke bondholders approve 60% extension',
    'Li Auto benefits from EV subsidy extension',
]

for headline in tests:
    score = client._analyze_sentiment(headline)
    print(f'{score:+.2f}: {headline[:40]}...')
"

# Expected output:
# +0.65: Pop Mart announces HK$251M share buyb...
# +0.60: MiniMax IPO debuts on HKEX...
# +0.75: Vanke bondholders approve 60% extensio...
# +0.60: Li Auto benefits from EV subsidy exte...

# Test full CLI
python3 data/news.py
```

### Phase 4: Integration Test (10 minutes)

```bash
# Run agent in scan mode (no trades)
python3 unified_agent.py --mode scan

# Check logs for catalyst detection
tail -20 logs/scan.log | grep -i catalyst
```

### Phase 5: Go Live

```bash
# If tests pass, restart the agent service
systemctl restart catalyst-intl

# Monitor logs
tail -f logs/agent.log
```

---

## HOT-RELOAD CAPABILITY

### Update Keywords Without Restart

```bash
# Edit the config file
nano config/news_context.yaml

# Add new keyword to positive_keywords:
#   - newkeyword

# Save and exit

# The agent will pick up changes on next news fetch
# OR force reload via Python:
python3 -c "
from data.news import reload_context
reload_context()
print('Context reloaded')
"
```

### Future Enhancement: Agent Self-Update

With this architecture, intl_claude could eventually update its own context:

```python
# Hypothetical future capability
async def learn_new_catalyst(self, keyword: str, tier: str):
    """Agent learns a new catalyst keyword from experience."""
    
    # Load current context
    with open("config/news_context.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    # Add new keyword
    if keyword not in config["positive_keywords"]:
        config["positive_keywords"].append(keyword)
        config["last_updated"] = datetime.now().isoformat()
        config["updated_by"] = "intl_claude"
        
        # Save
        with open("config/news_context.yaml", "w") as f:
            yaml.dump(config, f)
        
        # Reload
        reload_context()
        
        # Log learning
        await self.log_learning(f"Learned new catalyst keyword: {keyword}")
```

---

## VALIDATION CHECKLIST

### Pre-Deployment
- [ ] `news_context.yaml` has all 80+ positive keywords
- [ ] `news_context.yaml` has all 5 catalyst types with correct multipliers
- [ ] `news.py` loads context correctly
- [ ] PyYAML dependency installed

### Post-Deployment
- [ ] Context loads without errors
- [ ] Test headlines return expected sentiment scores
- [ ] Agent scan mode detects catalysts
- [ ] No errors in logs

### Weekly Validation
- [ ] Compare detected catalysts vs actual movers
- [ ] Add any missing keywords to config
- [ ] Adjust multipliers if needed

---

## FILE SUMMARY

| File | Location | Lines | Purpose |
|------|----------|-------|---------|
| `news_context.yaml` | config/ | ~350 | Editable context (keywords, types, sectors) |
| `news.py` | data/ | ~550 | Pure tool logic (loads from config) |

### news_context.yaml Structure

```yaml
version: "1.0.0"
last_updated: "2026-01-24"
updated_by: "craig"

positive_keywords:     # List of 80+ positive sentiment words
negative_keywords:     # List of 30 negative sentiment words

catalyst_types:        # 5 tiers
  binary_event:        # Tier 1, 1.5x multiplier
  corporate_action:    # Tier 2, 1.3x multiplier
  policy:              # Tier 3, 1.2x multiplier
  analyst:             # Tier 4, 1.0x multiplier
  general:             # Tier 5, 0.8x multiplier

sectors:               # HKEX sector groupings
  gold_jewelry:        # Laopu, CTF, Zijin, Zhaojin
  property:            # Vanke, CRL, COLI, Longfor
  ev_auto:             # Li, XPeng, Xiaomi, BYD
  ai_tech:             # Baidu, Tencent, Alibaba
  semiconductors:      # SMIC, Hua Hong, ASMPT
  banking:             # CCB, ICBC, BOC, HSBC
  insurance:           # Ping An, AIA, China Life

stock_names:           # Symbol → company name mapping

thresholds:            # Sentiment interpretation thresholds

composite_weights:     # Scoring weights (catalyst=40%, etc.)
```

### news.py Class Structure

```python
class NewsContext:
    """Loads context from YAML, supports hot-reload."""
    
class CatalystClassifier:
    """Classifies headlines into 5 catalyst tiers."""
    
class SectorTracker:
    """Detects sector-wide momentum for sympathy plays."""
    
class NewsClient:
    """Main API - fetches news, calculates sentiment."""
```

---

## EXPECTED OUTCOMES

| Metric | Before | After |
|--------|--------|-------|
| Positive keywords | 30 | 80+ |
| Catalyst detection rate | ~25% | >60% |
| Keywords update process | Edit code → restart | Edit YAML → auto-reload |
| Context version control | Mixed with code | Separate file |

---

## QUICK REFERENCE

### Commands

```bash
# SSH to droplet
ssh root@209.38.87.27

# Edit context
nano config/news_context.yaml

# Test sentiment
python3 -c "from data.news import NewsClient; c = NewsClient(); print(c._analyze_sentiment('buyback announced'))"

# Reload context
python3 -c "from data.news import reload_context; reload_context()"

# Run full test
python3 data/news.py

# Check agent logs
tail -f logs/agent.log
```

### File Locations

```
/root/catalyst-international/
├── config/
│   └── news_context.yaml    ← CONTEXT (edit this)
├── data/
│   └── news.py              ← TOOL (don't edit)
└── unified_agent.py         ← AGENT
```

---

*Implementation Plan v2.0.0 | Context-Separated Architecture | 2026-01-24*
