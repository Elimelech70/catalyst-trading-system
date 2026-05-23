# Catalyst Neural — Context-Conditioned Architecture Implementation

| Field | Value |
|---|---|
| Document | catalyst-context-conditioned-implementation |
| Version | 0.1 (DRAFT) |
| Created | 2026-05-23 |
| Last updated | 2026-05-23 |
| Updated by | Craig + Claude |
| Status | Implementation guide — awaiting design sign-off |
| Implements | `catalyst-context-conditioned-architecture.md` v0.1 |
| Related | `catalyst-neural-architecture-v0.3.md`, `catalyst-us-configuration-v1.0.md` |

## Revision history

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2026-05-23 | Craig + Claude | Initial implementation guide — 11 phases, pre-flight/verify/rollback per step |

---

## How to use this document

This guide is sequenced. Each phase has a clear **owner**, **pre-flight checks**, **steps**, **verify block**, **stop conditions**, and **rollback procedure**. Do not skip ahead. If any verify block fails, stop and consult Craig before proceeding.

**Owners:**

- `craig_laptop` — runs on Craig's laptop where catalyst-neural lives; Craig executes with Claude pairing
- `little_bro_us` — Claude Code on US droplet (`catalyst-trading-prod-01`)
- `little_bro_intl` — Claude Code on HKEX droplet
- `claude_assist` — pure analysis, document generation, or planning work; no execution

**Gates** mark mandatory stop points where results must be reviewed before continuing.

> ⚠️ **catalyst-agent status (2026-05-18):** catalyst-agent on the US droplet is **shelved** as of 2026-05-18 (see root `CLAUDE.md` v3.0.0). Phase 8 (Deploy to US droplet) is therefore **deferred** until catalyst-agent is un-shelved or its inference target is moved to another US-droplet host. The Phase 8 steps remain documented for that future restart; do not execute them now. v0.4 production deployment runs through Phase 9 (HKEX) only.

> ⚠️ **Deployed-schema reality (2026-05-23):** Audit of the laptop DB before Phase 1 found three deviations from earlier drafts of this doc. The doc has been corrected; future readers should rely on the corrected text below.
> - The candles schema is a **single `candles` table** with a `timeframe` column (values `'1m'`, `'5m'`, `'15m'`). There are not separate `candles_5m` / `candles_15m` tables. The dataset code in `training/dataset.py` already filters by timeframe — Phase 4 preserves this.
> - `securities.sector` **already exists** in `storage/database.py` (currently `NULL` on all 1,532 rows). Phase 1 does not re-add it; Phase 3 populates it.
> - The `news` table is empty (0 rows) at Phase 1 start. The regex tagger in Phase 2 still ships, but its initial backfill is a no-op; tagging is meaningful once `news_collector.py` starts producing rows.

---

## Overall pre-flight

Before ANY phase below, verify:

```bash
# 1. Working from clean git state on catalyst-trading-system
cd ~/catalyst-trading-system
git fetch origin
git status                  # must be clean or only have local design docs
git log --oneline -5        # confirm you know what's on HEAD

# 2. Catalyst-neural exists on laptop with a working v0.3 setup
cd ~/catalyst/catalyst-neural
ls models/                  # confirm at least one trained .pt and .onnx exists
python run.py labels --stats   # confirm labels exist
sqlite3 data/catalyst_neural.db "SELECT COUNT(*) FROM news;"
sqlite3 data/catalyst_neural.db "SELECT COUNT(*) FROM candles;"

# 3. Current production model version is recorded
cat catalyst-agent/models/model_version.json 2>/dev/null || echo "no model_version.json yet"
```

**Stop condition for overall pre-flight:** if catalyst-neural cannot produce a successful `python run.py train --model candle --dry-run` against current data, halt and fix the v0.3 pipeline first.

---

## Phase 1 — Schema migration

**Owner:** `craig_laptop` (SQLite changes); `claude_assist` writes the SQL

**Goal:** add new columns to `news`, `securities`, and create `context_regime_summary` table. Nothing else changes.

### Pre-flight

```bash
cd ~/catalyst/catalyst-neural
cp data/catalyst_neural.db data/catalyst_neural.db.pre-v04-backup
ls -lh data/catalyst_neural.db.pre-v04-backup    # confirm backup exists
```

### Steps

**1.1** Create migration script `storage/migrations/001_context_conditioning.sql`:

```sql
-- News table: category classification fields
ALTER TABLE news ADD COLUMN news_category_primary TEXT;
ALTER TABLE news ADD COLUMN news_category_secondary TEXT;
ALTER TABLE news ADD COLUMN news_category_tertiary TEXT;
ALTER TABLE news ADD COLUMN category_confidence REAL;
ALTER TABLE news ADD COLUMN classified_by TEXT;
ALTER TABLE news ADD COLUMN classified_at TEXT;

CREATE INDEX IF NOT EXISTS idx_news_category_primary
    ON news(news_category_primary);
CREATE INDEX IF NOT EXISTS idx_news_category_published
    ON news(news_category_primary, published_at);

-- Securities table: cap-tier classification
-- NOTE: securities.sector already exists in storage/database.py and on the deployed DB
-- (currently NULL on all 1,532 rows). Phase 3 populates it. Do NOT re-add it here.
ALTER TABLE securities ADD COLUMN market_cap_tier TEXT;
ALTER TABLE securities ADD COLUMN market_cap_usd REAL;
ALTER TABLE securities ADD COLUMN volatility_regime TEXT;     -- Phase 2 use, nullable
ALTER TABLE securities ADD COLUMN context_updated_at TEXT;

CREATE INDEX IF NOT EXISTS idx_securities_sector
    ON securities(sector);
CREATE INDEX IF NOT EXISTS idx_securities_cap_tier
    ON securities(market_cap_tier);

-- New table: context regime summary (analytics, not training)
CREATE TABLE IF NOT EXISTS context_regime_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_category TEXT NOT NULL,
    sector TEXT NOT NULL,
    cap_tier TEXT NOT NULL,
    market TEXT NOT NULL,
    sample_count INTEGER,
    mean_return_5m REAL,
    std_return_5m REAL,
    mean_return_15m REAL,
    std_return_15m REAL,
    mean_return_1h REAL,
    std_return_1h REAL,
    direction_bullish_pct REAL,
    direction_bearish_pct REAL,
    direction_neutral_pct REAL,
    last_computed TEXT,
    UNIQUE(news_category, sector, cap_tier, market)
);

CREATE INDEX IF NOT EXISTS idx_regime_lookup
    ON context_regime_summary(news_category, sector, cap_tier, market);
```

**1.2** Apply migration:

```bash
sqlite3 data/catalyst_neural.db < storage/migrations/001_context_conditioning.sql
```

**1.3** Update `storage/database.py` `init_db()` function so fresh databases get these columns natively. The migration SQL above is for the existing DB; the schema in `init_db()` must match the post-migration state.

### Verify

```bash
sqlite3 data/catalyst_neural.db ".schema news"        # confirm 6 new columns
sqlite3 data/catalyst_neural.db ".schema securities"  # confirm 4 new columns (sector pre-existed)
sqlite3 data/catalyst_neural.db ".schema context_regime_summary"   # confirm table exists
sqlite3 data/catalyst_neural.db "SELECT COUNT(*) FROM news;"  # row count unchanged
sqlite3 data/catalyst_neural.db "SELECT COUNT(*) FROM securities;"  # row count unchanged

# Run v0.3 training dry-run to confirm nothing breaks
python run.py train --model candle --dry-run
```

### Stop conditions

- Row counts changed after migration: STOP, restore from backup
- v0.3 dry-run fails: STOP, investigate

### Rollback

```bash
cp data/catalyst_neural.db.pre-v04-backup data/catalyst_neural.db
```

---

## Phase 2 — News tagging (regex baseline)

**Owner:** `craig_laptop` + `claude_assist` writes the code

**Goal:** classify every existing headline in `news` into the 15-category taxonomy using regex keyword matching. Tag new headlines at collection time going forward.

### Pre-flight

- Phase 1 verify passed
- Headlines exist: `sqlite3 data/catalyst_neural.db "SELECT COUNT(*) FROM news WHERE news_category_primary IS NULL;"` > 0

### Steps

**2.1** Create `storage/news_taxonomy.yaml` — the full keyword set per category. Start from `catalyst-international/config/news_context.yaml` and expand:

```yaml
# Each category has: priority (1=most specific, 5=most generic),
# match_keywords (list), boost_keywords (list, multiply confidence)
categories:
  earnings:
    priority: 2
    match_keywords:
      - earnings
      - reports
      - quarterly
      - Q1
      - Q2
      - Q3
      - Q4
      - revenue
      - EPS
      - guidance
      - outlook
      - profit
      - net income
    boost_keywords:
      - beat
      - miss
      - exceeded
      - shortfall
      - raises guidance
      - cuts guidance

  corporate_action:
    priority: 1
    match_keywords:
      - acquires
      - acquisition
      - merger
      - merges
      - takeover
      - buyback
      - repurchase
      - spinoff
      - spin-off
      - IPO
      - listing
      - debut
    boost_keywords:
      - announces
      - agreement
      - completes

  executive:
    priority: 1
    match_keywords:
      - CEO
      - CFO
      - resigns
      - resignation
      - appoints
      - appointed
      - founder
      - chairman
      - succession
      - departs
      - steps down

  regulatory_approval:
    priority: 1
    match_keywords:
      - FDA
      - approval
      - approved
      - approves
      - granted
      - clearance
      - cleared
      - ruling
      - verdict
      - settlement
      - decision
    boost_keywords:
      - drug
      - therapy
      - Phase 3
      - Phase II

  regulatory_action:
    priority: 1
    match_keywords:
      - SEC
      - lawsuit
      - sued
      - investigation
      - probe
      - subpoena
      - fine
      - charged
      - violation
      - antitrust

  bankruptcy:
    priority: 1
    match_keywords:
      - bankruptcy
      - default
      - restructuring
      - Chapter 11
      - insolvency
      - delisting

  product:
    priority: 3
    match_keywords:
      - launches
      - releases
      - unveils
      - partnership
      - collaboration
      - contract
      - order
      - deal
      - recall

  operational:
    priority: 3
    match_keywords:
      - production
      - factory
      - plant
      - strike
      - layoffs
      - layoff
      - supply
      - shortage
      - delays
      - shutdown

  analyst:
    priority: 2
    match_keywords:
      - upgrade
      - upgraded
      - downgrade
      - downgraded
      - initiates
      - initiated
      - price target
      - overweight
      - underweight
      - outperform
      - underperform
      - buy rating
      - sell rating

  credit_rating:
    priority: 1
    match_keywords:
      - Moody's
      - S&P
      - Fitch
      - credit rating
      - rating downgrade
      - rating upgrade
      - outlook negative
      - outlook positive

  monetary_policy:
    priority: 1
    match_keywords:
      - Fed
      - FOMC
      - Federal Reserve
      - rate hike
      - rate cut
      - basis points
      - Powell
      - PBOC
      - ECB
      - HKMA
      - Bank of England

  macro_economic:
    priority: 2
    match_keywords:
      - CPI
      - GDP
      - PPI
      - inflation
      - payrolls
      - unemployment
      - jobless claims
      - retail sales
      - trade deficit

  policy_regulation:
    priority: 2
    match_keywords:
      - tariff
      - sanction
      - subsidy
      - subsidies
      - stimulus
      - trade war
      - ban
      - restriction
      - executive order
      - legislation

  sector_wide:
    priority: 4
    match_keywords:
      - sector
      - industry
      - peers
      - sympathy

  capital:
    priority: 2
    match_keywords:
      - offering
      - dividend
      - distribution
      - debt issuance
      - bond issue
      - refinance
      - secondary offering
      - share issuance
```

**2.2** Create `storage/news_classifier_regex.py`:

```python
"""
Regex-based news classifier.
Loads news_taxonomy.yaml and assigns up to 3 categories per headline.
"""
import re
import yaml
from datetime import datetime
from pathlib import Path

TAXONOMY_PATH = Path(__file__).parent / "news_taxonomy.yaml"


def load_taxonomy():
    with open(TAXONOMY_PATH) as f:
        return yaml.safe_load(f)


def classify_headline(headline: str, taxonomy: dict) -> list[tuple[str, float]]:
    """
    Return [(category, confidence), ...] sorted descending, up to 3.
    Confidence is normalized 0-1.
    """
    headline_lower = headline.lower()
    scores = {}

    for category, config in taxonomy["categories"].items():
        priority = config["priority"]
        match_count = 0
        boost_count = 0

        for kw in config.get("match_keywords", []):
            if re.search(rf"\b{re.escape(kw.lower())}\b", headline_lower):
                match_count += 1

        for kw in config.get("boost_keywords", []):
            if re.search(rf"\b{re.escape(kw.lower())}\b", headline_lower):
                boost_count += 1

        if match_count == 0:
            continue

        # Score combines specificity (priority), match count, and boost
        # Higher priority (lower number) -> higher score
        priority_weight = (6 - priority) / 5.0   # priority 1 -> 1.0, priority 5 -> 0.2
        raw_score = match_count * priority_weight + boost_count * 0.5
        confidence = min(raw_score / 3.0, 1.0)   # cap at 1.0

        scores[category] = confidence

    if not scores:
        return [("other", 0.5)]

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return ranked[:3]


def classify_and_store(conn, news_id: int, headline: str, taxonomy: dict):
    """Classify one row and write back to the news table."""
    results = classify_headline(headline, taxonomy)
    primary = results[0][0] if len(results) > 0 else None
    secondary = results[1][0] if len(results) > 1 else None
    tertiary = results[2][0] if len(results) > 2 else None
    confidence = results[0][1] if len(results) > 0 else 0.0

    conn.execute("""
        UPDATE news
        SET news_category_primary = ?,
            news_category_secondary = ?,
            news_category_tertiary = ?,
            category_confidence = ?,
            classified_by = 'regex_v1',
            classified_at = ?
        WHERE id = ?
    """, (primary, secondary, tertiary, confidence,
          datetime.utcnow().isoformat(), news_id))


def backfill_all(conn, batch_size=1000):
    """Classify every unclassified headline in the news table."""
    taxonomy = load_taxonomy()
    total_done = 0

    while True:
        rows = conn.execute("""
            SELECT id, headline FROM news
            WHERE news_category_primary IS NULL
            LIMIT ?
        """, (batch_size,)).fetchall()

        if not rows:
            break

        for row in rows:
            classify_and_store(conn, row["id"], row["headline"], taxonomy)

        conn.commit()
        total_done += len(rows)
        print(f"  Classified {total_done} headlines...")

    return total_done
```

**2.3** Wire into `run.py`:

```python
def cmd_tag_news():
    """Backfill news category classifications."""
    from storage.news_classifier_regex import backfill_all
    from storage.database import get_connection

    init_db()
    conn = get_connection()
    total = backfill_all(conn)
    conn.close()
    print(f"\nClassified {total} headlines.")
```

**2.4** Run backfill:

```bash
python run.py tag-news
```

**2.5** Update `collectors/news_collector.py` to call `classify_and_store` on every new headline insert.

### Verify

```bash
# Spot-check category distribution
sqlite3 data/catalyst_neural.db "
SELECT news_category_primary, COUNT(*) as cnt
FROM news
WHERE news_category_primary IS NOT NULL
GROUP BY news_category_primary
ORDER BY cnt DESC;
"

# Sample manual review — pull 20 random headlines + assigned category
sqlite3 data/catalyst_neural.db "
SELECT news_category_primary, category_confidence, headline
FROM news
WHERE news_category_primary IS NOT NULL
ORDER BY RANDOM()
LIMIT 20;
"
```

**Manual review criterion:** at least 16 of the 20 random samples should be intuitively correct. If fewer, the taxonomy keywords need tuning before proceeding.

### Stop conditions

- More than 40% of headlines classified as `other` → keyword sets too narrow; tune the yaml
- A single category captures >60% → keyword sets too greedy in that category; tune the yaml
- Manual review accuracy <80% → STOP and tune before moving to Phase 3

### Rollback

```bash
sqlite3 data/catalyst_neural.db "
UPDATE news SET
  news_category_primary = NULL,
  news_category_secondary = NULL,
  news_category_tertiary = NULL,
  category_confidence = NULL,
  classified_by = NULL,
  classified_at = NULL;
"
```

---

## Phase 3 — Security tagging

**Owner:** `craig_laptop` (mostly manual + spreadsheet)

**Goal:** populate `sector`, `market_cap_tier`, `market_cap_usd` for every active security.

### Pre-flight

```bash
sqlite3 data/catalyst_neural.db "SELECT COUNT(*) FROM securities WHERE active = 1;"
```

If this number is small (<200), manual is faster than scraping. If larger, automate via Yahoo Finance or similar.

### Steps

**3.1** Export active securities:

```bash
sqlite3 data/catalyst_neural.db -header -csv "
SELECT symbol, market FROM securities WHERE active = 1 ORDER BY market, symbol;
" > /tmp/securities_to_tag.csv
```

**3.2** Tag the CSV with `sector` (one of 11 IDs) and `market_cap_tier` (MICRO/SMALL/MID/LARGE/MEGA) using either:

- Manual fill from public data (Yahoo Finance, Bloomberg terminal); or
- Yahoo Finance API lookup via a tagger script (see 3.4 below)

**3.3** Reference tables for sector and cap-tier definitions are in `catalyst-context-conditioned-architecture.md` sections 4.2 and 4.3.

**3.4** (Optional) Auto-tagger script `storage/security_classifier.py`:

```python
"""
Auto-tag securities using yfinance metadata.
Manual override always wins.
"""
import yfinance as yf
from datetime import datetime

SECTOR_MAP = {
    # yfinance returns sectors like "Technology", "Healthcare", etc.
    # Map them to our 11 sector IDs.
    "Technology": "TECH",
    "Healthcare": "BIO",                # crude — will need refinement for non-biotech
    "Financial Services": "FIN",
    "Consumer Cyclical": "CONS_D",
    "Consumer Defensive": "CONS_S",
    "Energy": "ENERGY",
    "Industrials": "INDUSTRIAL",
    "Basic Materials": "MATERIALS",
    "Utilities": "UTIL",
    "Communication Services": "COMMS",
    "Real Estate": "REAL_ESTATE",
}


def cap_tier_from_usd(cap_usd: float) -> str:
    if cap_usd is None or cap_usd <= 0:
        return None
    if cap_usd < 3e8:
        return "MICRO"
    if cap_usd < 2e9:
        return "SMALL"
    if cap_usd < 1e10:
        return "MID"
    if cap_usd < 2e11:
        return "LARGE"
    return "MEGA"


def fetch_security_meta(symbol: str, market: str) -> dict:
    """Fetch sector + market cap from yfinance."""
    ticker_symbol = symbol if market == "US" else f"{int(symbol):04d}.HK"
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info
        sector_raw = info.get("sector") or info.get("sectorKey")
        sector = SECTOR_MAP.get(sector_raw)
        cap_usd = info.get("marketCap")
        if market != "US" and cap_usd:
            # Convert HKD to USD at 7.8
            cap_usd = cap_usd / 7.8
        return {
            "sector": sector,
            "market_cap_usd": cap_usd,
            "market_cap_tier": cap_tier_from_usd(cap_usd),
        }
    except Exception as e:
        print(f"  {symbol} ({market}): {e}")
        return {}


def backfill_securities(conn):
    rows = conn.execute(
        "SELECT symbol, market FROM securities WHERE active = 1 "
        "AND (sector IS NULL OR market_cap_tier IS NULL)"
    ).fetchall()

    for r in rows:
        meta = fetch_security_meta(r["symbol"], r["market"])
        if not meta:
            continue
        conn.execute("""
            UPDATE securities
            SET sector = COALESCE(?, sector),
                market_cap_usd = COALESCE(?, market_cap_usd),
                market_cap_tier = COALESCE(?, market_cap_tier),
                context_updated_at = ?
            WHERE symbol = ? AND market = ?
        """, (meta.get("sector"), meta.get("market_cap_usd"),
              meta.get("market_cap_tier"),
              datetime.utcnow().isoformat(),
              r["symbol"], r["market"]))
        conn.commit()
        print(f"  {r['symbol']} ({r['market']}): "
              f"{meta.get('sector')} / {meta.get('market_cap_tier')}")
```

**3.5** Manual override pass — for biotech-vs-pharma distinction, HKEX names yfinance doesn't tag well, and edge cases. Save overrides in `storage/security_overrides.yaml` and re-apply if backfill runs again.

### Verify

```bash
# All active securities tagged
sqlite3 data/catalyst_neural.db "
SELECT
  COUNT(*) FILTER (WHERE sector IS NOT NULL) as tagged_sector,
  COUNT(*) FILTER (WHERE market_cap_tier IS NOT NULL) as tagged_cap,
  COUNT(*) as total_active
FROM securities WHERE active = 1;
"

# Sector distribution
sqlite3 data/catalyst_neural.db "
SELECT market, sector, market_cap_tier, COUNT(*) as cnt
FROM securities WHERE active = 1
GROUP BY market, sector, market_cap_tier
ORDER BY market, cnt DESC;
"
```

### Stop conditions

- More than 10% of active securities still untagged after auto + manual pass → tag them as `other` / `MID` defaults rather than blocking, but flag for Craig

### Rollback

```sql
UPDATE securities SET
  sector = NULL,
  market_cap_tier = NULL,
  market_cap_usd = NULL,
  context_updated_at = NULL
WHERE active = 1;
```

---

## GATE A — Hypothesis validation (Test 1)

**Owner:** `claude_assist` + `craig_laptop`

**Goal:** before investing in v0.4 model work, validate on real data that news category × security type produces statistically distinguishable return distributions. If this fails, the hypothesis is wrong for this data and we do not proceed.

### Pre-flight

- Phases 1, 2, 3 verify all passed
- Forward returns exist: `sqlite3 data/catalyst_neural.db "SELECT COUNT(*) FROM forward_returns WHERE return_5m IS NOT NULL;"`

### Steps

**A.1** Create `storage/context_regime.py`:

```python
"""
Populate context_regime_summary table by joining:
  forward_returns + news (joined by symbol + time window) + securities
"""
import numpy as np
from datetime import datetime, timedelta

NEWS_LOOKBACK_HOURS = 4


def compute_all_regimes(conn):
    """For every (news_category, sector, cap_tier, market) cell, compute stats."""

    # Build sample-level table in memory: each forward_return row tagged with
    # dominant news category in the lookback window + the security's context.
    rows = conn.execute("""
        SELECT
          fr.symbol, fr.market, fr.timestamp,
          fr.return_5m, fr.return_15m, fr.return_1h,
          s.sector, s.market_cap_tier
        FROM forward_returns fr
        JOIN securities s ON s.symbol = fr.symbol AND s.market = fr.market
        WHERE fr.timeframe = '5m'
          AND fr.return_5m IS NOT NULL
          AND s.sector IS NOT NULL
          AND s.market_cap_tier IS NOT NULL
    """).fetchall()

    samples = []
    for r in rows:
        ts = r["timestamp"]
        # Find dominant news category in lookback window
        cutoff = (datetime.fromisoformat(ts.replace("+00:00", ""))
                  - timedelta(hours=NEWS_LOOKBACK_HOURS)).isoformat()
        news = conn.execute("""
            SELECT news_category_primary
            FROM news
            WHERE published_at >= ? AND published_at <= ?
              AND (symbols LIKE ? OR symbols LIKE ? OR symbols = ?)
              AND news_category_primary IS NOT NULL
            ORDER BY category_confidence DESC
            LIMIT 1
        """, (cutoff, ts, f"%,{r['symbol']},%", f"{r['symbol']},%", r["symbol"])
        ).fetchone()

        category = news["news_category_primary"] if news else "no_news"
        samples.append({
            "news_category": category,
            "sector": r["sector"],
            "cap_tier": r["market_cap_tier"],
            "market": r["market"],
            "return_5m": r["return_5m"],
            "return_15m": r["return_15m"],
            "return_1h": r["return_1h"],
        })

    # Aggregate per cell
    from collections import defaultdict
    groups = defaultdict(list)
    for s in samples:
        key = (s["news_category"], s["sector"], s["cap_tier"], s["market"])
        groups[key].append(s)

    # Write summary rows
    conn.execute("DELETE FROM context_regime_summary;")
    now = datetime.utcnow().isoformat()
    for (ncat, sector, tier, mkt), sample_list in groups.items():
        n = len(sample_list)
        r5 = [s["return_5m"] for s in sample_list if s["return_5m"] is not None]
        r15 = [s["return_15m"] for s in sample_list if s["return_15m"] is not None]
        r1h = [s["return_1h"] for s in sample_list if s["return_1h"] is not None]

        bull = sum(1 for x in r5 if x > 0.05) / max(len(r5), 1) * 100
        bear = sum(1 for x in r5 if x < -0.05) / max(len(r5), 1) * 100
        neutral = 100 - bull - bear

        conn.execute("""
            INSERT INTO context_regime_summary (
              news_category, sector, cap_tier, market,
              sample_count, mean_return_5m, std_return_5m,
              mean_return_15m, std_return_15m,
              mean_return_1h, std_return_1h,
              direction_bullish_pct, direction_bearish_pct, direction_neutral_pct,
              last_computed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ncat, sector, tier, mkt, n,
              float(np.mean(r5)) if r5 else None,
              float(np.std(r5)) if r5 else None,
              float(np.mean(r15)) if r15 else None,
              float(np.std(r15)) if r15 else None,
              float(np.mean(r1h)) if r1h else None,
              float(np.std(r1h)) if r1h else None,
              bull, bear, neutral, now))

    conn.commit()
    return len(groups)
```

**A.2** Run distribution analysis:

```bash
python -c "
from storage.database import get_connection
from storage.context_regime import compute_all_regimes
conn = get_connection()
n = compute_all_regimes(conn)
print(f'Computed {n} regime cells')
"
```

**A.3** Inspect well-populated cells:

```bash
sqlite3 data/catalyst_neural.db "
SELECT news_category, sector, cap_tier, market, sample_count,
       ROUND(mean_return_5m, 4) as mean_5m,
       ROUND(std_return_5m, 4) as std_5m,
       ROUND(direction_bullish_pct, 1) as bull_pct
FROM context_regime_summary
WHERE sample_count >= 100
ORDER BY sample_count DESC
LIMIT 50;
"
```

**A.4** Run pairwise KS tests on a handful of intuitively-different cells (e.g., `regulatory_approval × BIO × SMALL` vs `earnings × TECH × LARGE`). A Python notebook or one-shot script using `scipy.stats.ks_2samp` is sufficient.

### Verify (this is the GATE)

The hypothesis is supported if **at least 5 pairs of well-populated cells (≥100 samples each)** show KS p-values < 0.01 — meaning their return distributions are statistically distinguishable.

### Stop conditions

- Fewer than 5 statistically-different pairs → STOP. The hypothesis is not supported by this data. Reconvene with Craig to decide whether the issue is (a) too little data, (b) bad classification, or (c) the hypothesis is genuinely wrong for this universe.
- Most cells have <30 samples → STOP. Data volume too low to model context conditioning meaningfully. Collect more data, then retry.

### If GATE A passes

Proceed to Phase 4. Otherwise, halt the v0.4 program.

---

## Phase 4 — Dataset v0.4

**Owner:** `craig_laptop` + `claude_assist` writes the code

**Goal:** extend `CandleDataset` to return `news_context` and `security_context` per sample.

### Pre-flight

- GATE A passed

### Steps

**4.1** Create `training/context_features.py`:

```python
"""
Build news and security context vectors for the v0.4 candle dataset.
"""
import numpy as np
from datetime import datetime, timedelta

NEWS_CATEGORIES = [
    "earnings", "corporate_action", "executive", "capital",
    "regulatory_approval", "regulatory_action", "bankruptcy",
    "product", "operational",
    "analyst", "credit_rating",
    "monetary_policy", "macro_economic", "policy_regulation", "sector_wide",
    "other",   # 16th slot for catch-all
]
NEWS_CATEGORY_INDEX = {c: i for i, c in enumerate(NEWS_CATEGORIES)}
NEWS_CONTEXT_DIM = len(NEWS_CATEGORIES)  # 16

SECTORS = ["TECH", "BIO", "FIN", "CONS_D", "CONS_S", "ENERGY",
           "INDUSTRIAL", "MATERIALS", "UTIL", "COMMS", "REAL_ESTATE"]
SECTOR_INDEX = {s: i for i, s in enumerate(SECTORS)}
SECTOR_DIM = len(SECTORS)  # 11

CAP_TIERS = ["MICRO", "SMALL", "MID", "LARGE", "MEGA"]
CAP_TIER_INDEX = {c: i for i, c in enumerate(CAP_TIERS)}
CAP_TIER_DIM = len(CAP_TIERS)  # 5

MARKETS = ["US", "HKEX"]
MARKET_INDEX = {m: i for i, m in enumerate(MARKETS)}
MARKET_DIM = len(MARKETS)  # 2

SECURITY_CONTEXT_DIM = MARKET_DIM + SECTOR_DIM + CAP_TIER_DIM  # 18

NEWS_LOOKBACK_HOURS = 4
SOURCE_TIER_WEIGHTS = {1: 1.5, 2: 1.3, 3: 1.0, 4: 0.8}


def build_news_context(news_rows, candle_ts):
    """
    Build a 16-dim news context vector.

    news_rows: list of dicts with keys
      published_at, news_category_primary, news_category_secondary,
      source_tier
    candle_ts: ISO timestamp string of the candle being scored.
    """
    vec = np.zeros(NEWS_CONTEXT_DIM, dtype=np.float32)
    if not news_rows:
        return vec

    try:
        ts = datetime.fromisoformat(candle_ts.replace("+00:00", ""))
    except ValueError:
        return vec

    for r in news_rows:
        try:
            pub = datetime.fromisoformat(
                r["published_at"].replace("+00:00", "").replace("Z", ""))
        except ValueError:
            continue
        hours_before = (ts - pub).total_seconds() / 3600.0
        if hours_before < 0 or hours_before > NEWS_LOOKBACK_HOURS:
            continue

        recency_decay = 1.0 - (hours_before / NEWS_LOOKBACK_HOURS)
        tier_weight = SOURCE_TIER_WEIGHTS.get(r.get("source_tier") or 3, 1.0)
        weight = recency_decay * tier_weight

        # Primary category at full weight, secondary at half
        primary = r.get("news_category_primary")
        if primary in NEWS_CATEGORY_INDEX:
            vec[NEWS_CATEGORY_INDEX[primary]] += weight
        secondary = r.get("news_category_secondary")
        if secondary in NEWS_CATEGORY_INDEX:
            vec[NEWS_CATEGORY_INDEX[secondary]] += weight * 0.5

    # L1 normalize so vector sums to 1 (or stays 0)
    total = vec.sum()
    if total > 0:
        vec = vec / total
    return vec


def build_security_context(market, sector, cap_tier):
    """Build an 18-dim security context vector (one-hot concat)."""
    vec = np.zeros(SECURITY_CONTEXT_DIM, dtype=np.float32)

    if market in MARKET_INDEX:
        vec[MARKET_INDEX[market]] = 1.0
    if sector in SECTOR_INDEX:
        vec[MARKET_DIM + SECTOR_INDEX[sector]] = 1.0
    if cap_tier in CAP_TIER_INDEX:
        vec[MARKET_DIM + SECTOR_DIM + CAP_TIER_INDEX[cap_tier]] = 1.0
    return vec
```

**4.2** Extend `training/dataset.py` `CandleDataset` to:

- Load news rows joined with categories
- Load security metadata (sector, cap_tier) into a per-symbol cache
- In `__getitem__`, call `build_news_context(...)` and `build_security_context(...)`
- Return them alongside the existing fields

**4.3** Add a dry-run smoke test in `run.py`:

```python
def cmd_inspect_context_sample():
    """Show what a v0.4 sample looks like."""
    from training.dataset import CandleDataset
    ds = CandleDataset(split="train")
    sample = ds[0]
    print(f"candles_5m shape: {sample['candles_5m'].shape}")
    print(f"news_context: {sample['news_context'].numpy()}")
    print(f"security_context: {sample['security_context'].numpy()}")
    print(f"direction: {sample['direction'].item()}")
```

### Verify

```bash
python run.py inspect-context-sample
# Expect: candles shapes correct, news_context is 16 floats summing to 0 or 1,
# security_context is 18 floats with exactly 3 ones, direction in {0, 1, 2}
```

### Stop conditions

- News context is all-zero for >80% of samples → news join logic is broken; check the symbols matching in 4.1
- Security context isn't summing to exactly 3 → encoding bug

### Rollback

Revert `training/dataset.py` from git; v0.3 dataset class continues to work.

---

## Phase 5 — Model v0.4

**Owner:** `craig_laptop` + `claude_assist` writes the code

### Pre-flight

- Phase 4 verify passed

### Steps

**5.1** In `training/models.py`, add `ContextEncoder` (see design doc section 9.2).

**5.2** Modify `CandleModel` `__init__` to accept context dims and instantiate `ContextEncoder`. Resize `input_proj` from `fusion_input` (128) to `fusion_input + context_embed_dim` (160).

**5.3** Modify `CandleModel.forward` to accept 4 inputs and concatenate context_embed to candle_fused before the fusion MLP.

**5.4** Modify `CandleTrainer.train_epoch` and `validate` to pass the 4 inputs through `self.model(...)`.

**5.5** Add new diagnostic in `report.py`:

- Per-news-category direction accuracy table (16 rows)
- Per-sector direction accuracy table (11 rows)
- Per-cap-tier direction accuracy table (5 rows)
- Joint heatmap: news × sector
- Joint heatmap: news × cap_tier

### Verify

```bash
# Parameter count sanity check
python run.py train --model candle --dry-run
# Expect: parameters ~141K, all encoder counts print, no crashes
```

### Stop conditions

- Parameter count differs from expected by more than 5K → architecture bug
- Forward pass crashes → shape mismatch somewhere; trace it

### Rollback

Revert `training/models.py` and `training/trainer.py` from git.

---

## Phase 6 — Training run (Test 2)

**Owner:** `craig_laptop`

### Pre-flight

- Phase 5 verify passed
- GPU available: `nvidia-smi`

### Steps

**6.1** Train v0.4:

```bash
python run.py train --model candle 2>&1 | tee logs/v04_training_$(date +%Y%m%d_%H%M%S).log
```

**6.2** Train a fresh v0.3 baseline on the same data window for fair comparison:

```bash
# Tag the v0.3 run for clarity
git stash  # set aside v0.4 model code
git checkout HEAD~1 -- training/models.py training/trainer.py   # restore v0.3
python run.py train --model candle 2>&1 | tee logs/v03_baseline_$(date +%Y%m%d_%H%M%S).log
git stash pop
```

**6.3** Open both HTML training reports and compare side-by-side.

### Verify (Test 2 GATE)

Test 2 passes if BOTH:

- v0.4 direction accuracy ≥ v0.3 direction accuracy + 5 percentage points, on the full validation set
- v0.4 outperforms v0.3 on at least 8 of 15 news categories (excluding `other`)

### Stop conditions

- v0.4 worse than v0.3: STOP. Either context isn't being learned (check ContextEncoder gradients) or the hypothesis is failing on this data. Do not deploy v0.4 to production.
- v0.4 better overall but worse on rare-but-high-impact categories (e.g., regulatory_approval): consider category-weighted loss in a v0.4.1 retrain.

### Rollback

v0.3 models remain in `models/` directory; v0.4 model checkpoints are just additional files. Nothing to roll back.

---

## Phase 7 — ONNX export and validation

**Owner:** `craig_laptop`

### Steps

**7.1** Export v0.4 to ONNX with 4 inputs:

```python
torch.onnx.export(
    model,
    (candles_5m_sample, candles_15m_sample, news_ctx_sample, security_ctx_sample),
    "models/candle_model_v04.onnx",
    input_names=["candles_5m", "candles_15m", "news_context", "security_context"],
    output_names=["direction_logits", "pred_returns", "confidence"],
    dynamic_axes={
        "candles_5m": {0: "batch"},
        "candles_15m": {0: "batch"},
        "news_context": {0: "batch"},
        "security_context": {0: "batch"},
    },
    opset_version=14,
)
```

**7.2** Update `models/model_version.json`:

```json
{
  "model_type": "candle",
  "version": "0.4",
  "exported_at": "...",
  "inputs": ["candles_5m", "candles_15m", "news_context", "security_context"],
  "input_shapes": {
    "candles_5m": [60, 5],
    "candles_15m": [60, 5],
    "news_context": [16],
    "security_context": [18]
  },
  "supersedes": "0.3"
}
```

**7.3** Validate ONNX inference matches PyTorch within tolerance (<1e-5 difference on 100 sample batch).

### Verify

```bash
python -c "
import onnxruntime as ort
import numpy as np
sess = ort.InferenceSession('models/candle_model_v04.onnx')
print([i.name for i in sess.get_inputs()])
print([o.name for o in sess.get_outputs()])
"
```

### Stop conditions

- ONNX outputs differ from PyTorch by >1e-3: export bug, do not deploy

---

## Phase 8 — Deploy to US droplet

**Owner:** `little_bro_us`

### Pre-flight

```bash
# On the droplet
ssh catalyst-trading-prod-01
df -h /var/lib/catalyst                    # disk space
ls -lh /var/lib/catalyst/models/            # existing models
cat /var/lib/catalyst/models/model_version.json 2>/dev/null
docker ps | grep neural                     # neural container running
```

### Steps

**8.1** Craig SCPs the new model:

```bash
# From laptop
scp models/candle_model_v04.onnx \
    catalyst-trading-prod-01:/var/lib/catalyst/models/

scp models/model_version.json \
    catalyst-trading-prod-01:/var/lib/catalyst/models/
```

**8.2** `little_bro_us` updates the neural container's inference path to read 4 inputs. Identify the loader file (likely `agents/neural/cerebellum_loader.py` or similar in `catalyst-agent`):

- Update ONNX session input names
- Build runtime news context from the local news DB (same logic as `training/context_features.py`)
- Build security context from securities table (cache per symbol)

**8.3** Restart neural container:

```bash
docker compose -f /root/catalyst-agent/docker-compose.yml restart neural
```

### Verify

```bash
# Cycle through and confirm neural is producing outputs
docker logs catalyst-neural --tail 100 | grep -i "prediction"
sqlite3 /var/lib/catalyst/db/agent.db "
SELECT COUNT(*) FROM neural_predictions
WHERE created_at > datetime('now', '-10 minutes');
"
```

### Stop conditions

- Neural container crash-loops: revert `model_version.json` to v0.3, restart
- Predictions empty after 10 min: log shape mismatch likely; investigate before continuing

### Rollback

```bash
# little_bro_us
cp /var/lib/catalyst/models/model_version_v03_backup.json \
   /var/lib/catalyst/models/model_version.json
docker compose -f /root/catalyst-agent/docker-compose.yml restart neural
```

---

## Phase 9 — Deploy to HKEX droplet

**Owner:** `little_bro_intl`

### Pre-flight

```bash
ssh catalyst-intl-droplet
ls -lh /root/catalyst-international/models/
ps aux | grep cerebellum
```

### Steps

**9.1** Craig SCPs the model:

```bash
scp models/candle_model_v04.onnx \
    catalyst-intl-droplet:/root/catalyst-international/models/
```

**9.2** `little_bro_intl` updates `cerebellum.py`:

- The existing `CandleModel` class (in HKEX `cerebellum.py`) needs to accept 4 inputs
- Build runtime news context using `catalyst_intl` PostgreSQL news rows
- Build security context from the securities table or YAML config
- Maintain compatibility shim so the 5-tier HKEX catalyst types map into the 15-category scheme during the transition (see compatibility table in design doc section 3.3)

**9.3** Restart the HKEX coordinator with the new cerebellum:

```bash
sudo systemctl restart catalyst-international
# or whatever the process control is
```

### Verify

```bash
psql $DATABASE_URL -c "
SELECT COUNT(*) FROM cr_neural_predictions
WHERE created_at > NOW() - INTERVAL '10 minutes';
"
```

### Stop conditions

- HKEX trading would be live; if cerebellum fails, the coordinator should fall back to no-signal (Attention State Machine Mode 1) automatically. Confirm this happens.
- If it doesn't fall back cleanly: revert immediately.

### Rollback

Restore prior `cerebellum.py` from git; restart coordinator.

---

## Phase 10 — Test 3 (production fruit, 30-day measurement)

**Owner:** `little_bro_us` and `little_bro_intl` (passive monitoring)

### Pre-flight

Phases 8 and 9 deployed and stable for at least 48 hours.

### Steps

**10.1** Each agent records every prediction in the `neural_predictions` table along with the (news_category, sector, cap_tier) context at prediction time.

**10.2** Each closed position records the entry prediction, exit type, and actual return in the `production_outcomes` table.

**10.3** Weekly job joins predictions to outcomes and computes:

- Direction accuracy on closed positions, overall and per joint cell
- Stop loss rate week-over-week
- Confidence calibration (do 80% confidence predictions win ~80%?)

### Verify (Test 3 GATE — measured at day 30)

Test 3 passes if ALL:

- Stop loss rate ≥30% lower than the 30 days pre-v0.4
- Direction accuracy on closed positions ≥ 55%
- Confidence is positively correlated with win rate (high confidence wins more often than low confidence)

### Stop conditions

If Test 3 fails at day 30:

- Stop loss rate unchanged or worse: the model isn't catching reversals any better than before. Revisit ContextEncoder design (consider Option 2 FiLM).
- Confidence inverted (high confidence loses more): the model is overconfident on regimes it has not learned. Likely cause: rare-category samples too few. Add category-weighted loss.

### Rollback

If Test 3 fails outright (worse than v0.3), revert both droplets to v0.3 ONNX. The schema and tagging stay (they're prerequisites for any v0.4.x retry).

---

## Phase 11 — LLM news classifier (Phase 1.5)

**Owner:** `craig_laptop` + `claude_assist`

**Defer until:** Test 2 and Test 3 both passed. This is an accuracy upgrade to the regex tagger, not a prerequisite.

### Steps

**11.1** Write `storage/news_classifier_llm.py` that:

- Selects headlines where `category_confidence < 0.5` from the regex pass
- Sends them to Claude in batches with a structured-output prompt enumerating the 15 categories
- Stores results with `classified_by = 'llm_v1'`

**11.2** Compare LLM vs regex on overlap; flag disagreements for human review.

**11.3** When sufficient validated examples accumulate (~5,000+), consider training a small RoBERTa classifier per the LabelFusion paper findings.

---

## Files manifest

### To be created

```
catalyst-neural/storage/migrations/001_context_conditioning.sql
catalyst-neural/storage/news_taxonomy.yaml
catalyst-neural/storage/news_classifier_regex.py
catalyst-neural/storage/news_classifier_llm.py             # Phase 11
catalyst-neural/storage/security_classifier.py
catalyst-neural/storage/security_overrides.yaml
catalyst-neural/storage/context_regime.py
catalyst-neural/training/context_features.py
catalyst-trading-system/Documentation/Design/catalyst-news-taxonomy.md   # standalone reference
```

### To be modified

```
catalyst-neural/storage/database.py             # init_db() to include new columns
catalyst-neural/collectors/news_collector.py    # tag at collection time
catalyst-neural/training/dataset.py             # CandleDataset v0.4
catalyst-neural/training/models.py              # ContextEncoder + CandleModel v0.4
catalyst-neural/training/trainer.py             # 4-input forward
catalyst-neural/training/report.py              # context diagnostics
catalyst-neural/run.py                          # new commands: tag-news, tag-securities, distributions, inspect-context-sample
catalyst-agent/agents/neural/cerebellum_loader.py    # 4-input ONNX
catalyst-international/cerebellum.py            # 4-input ONNX + compatibility shim
catalyst-international/config/news_context.yaml      # mapping to 15-category scheme
```

### To be marked as superseded

```
catalyst-neural-architecture-v0.3.md           # input section
```

### GitHub commits

All four implementations (`catalyst-international`, `catalyst-neural`, `catalyst-agent`, `catalyst-research`) now live in the `catalyst-trading-system` GitHub repo (as of the 2026-05-18 consolidation). Per `Documentation/Implementation/catalyst-repo-hygiene.md`: pull-before-work, push-after-work, never force-push on main, never commit `.env` or large model artifacts. Edits to a given subsystem are owned by that subsystem's host (laptop owns `catalyst-neural`, intl droplet owns `catalyst-international`, etc.) but the source of truth is the GitHub repo.

Commit sequence after each successful phase:

```bash
cd ~/catalyst-trading-system
git fetch origin
git reset --hard origin/main      # if little_bro has been pushing during the session
git add Documentation/Design/catalyst-context-conditioned-architecture-v0.1.md
git add Documentation/Implementation/catalyst-context-conditioned-implementation-v0.1.md
git commit -m "design: context-conditioned architecture v0.4 plan + implementation guide"
git push https://<TOKEN>@github.com/Elimelech70/catalyst-trading-system.git main
```

---

## Estimated calendar timeline

| Phase | Active work | Calendar |
|---|---|---|
| 1. Schema migration | 1 hour | Day 1 |
| 2. Regex tagging | 1 day | Day 1-2 |
| 3. Security tagging | 0.5 day | Day 2 |
| GATE A. Test 1 | 0.5 day | Day 3 |
| 4. Dataset v0.4 | 1 day | Day 4 |
| 5. Model v0.4 | 0.5 day | Day 4-5 |
| 6. Training (Test 2) | 0.5 day | Day 5 |
| 7. ONNX export | 0.5 day | Day 6 |
| 8. US deployment | 0.5 day | Day 6 |
| 9. HKEX deployment | 1 day | Day 7 |
| 10. Test 3 monitoring | passive | Days 8-38 |
| 11. LLM classifier | 1 day | Day 39+ (only if Tests pass) |

Total active engineering: ~7 days. Calendar end-to-end: ~5.5 weeks with the 30-day production fruit measurement window.

---

## Risk-driven STOP conditions summary

The single most important rule: **never deploy v0.4 to production if Test 2 fails**. The system trading with a degraded model is worse than the system not trading with v0.3.

If Test 1 fails: data doesn't support the hypothesis. Stop.
If Test 2 fails: model isn't learning the context. Stop, debug.
If Test 3 fails: model trained well but doesn't generalize to production. Revert; rethink.

Every gate is a real gate. The temptation will be to push through "just to ship". Resist it. The cost of a bad model in production is higher than the cost of slower iteration.

---

## End of document
