# International Droplet Cleanup - Implementation Guide

**Name of Application:** Catalyst Trading System  
**Name of file:** international-cleanup-implementation.md  
**Version:** 1.0.0  
**Last Updated:** 2026-02-01  
**Purpose:** Step-by-step implementation guide for Claude Code on international droplet  
**Scope:** Remove consciousness/email, add database logging

---

## REVISION HISTORY

- v1.0.0 (2026-02-01) - Initial implementation guide

---

## Overview

This guide instructs Claude Code on the International Droplet to:
1. Remove all consciousness framework code
2. Remove all email/SMTP alert code
3. Add database logging for observability
4. Update configuration files
5. Test the changes

**Goal:** Pure trading system with all logs going to `catalyst_intl.agent_logs` table.

---

## Pre-Flight Checklist

Before starting, verify:

```bash
# SSH to international droplet
ssh root@137.184.244.45

# Check current directory
cd /root/Catalyst-Trading-System-International/catalyst-international

# Verify files exist
ls -la unified_agent.py tool_executor.py position_monitor_service.py

# Backup current state
mkdir -p /root/backups/$(date +%Y%m%d)
cp *.py /root/backups/$(date +%Y%m%d)/
cp .env /root/backups/$(date +%Y%m%d)/
cp config/*.yaml /root/backups/$(date +%Y%m%d)/
```

---

## Phase 1: Database Schema Update

### Step 1.1: Add agent_logs Table

Connect to catalyst_intl and run:

```sql
-- Connect to database
psql $DATABASE_URL

-- Create agent_logs table
CREATE TABLE IF NOT EXISTS agent_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    level VARCHAR(20) NOT NULL,
    source VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    context JSONB,
    cycle_id VARCHAR(50),
    symbol VARCHAR(20),
    error_type VARCHAR(100),
    stack_trace TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp ON agent_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_logs_level ON agent_logs(level);
CREATE INDEX IF NOT EXISTS idx_agent_logs_source ON agent_logs(source);
CREATE INDEX IF NOT EXISTS idx_agent_logs_symbol ON agent_logs(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_logs_cycle ON agent_logs(cycle_id);
CREATE INDEX IF NOT EXISTS idx_agent_logs_errors ON agent_logs(timestamp DESC) 
    WHERE level IN ('ERROR', 'CRITICAL');

-- Verify
\d agent_logs
```

---

## Phase 2: Create Database Logger

### Step 2.1: Create db_logger.py

Create new file `/root/Catalyst-Trading-System-International/catalyst-international/db_logger.py`:

```python
"""
Name of Application: Catalyst Trading System
Name of file: db_logger.py
Version: 1.0.0
Last Updated: 2026-02-01
Purpose: Database logging handler for observability

REVISION HISTORY:
v1.0.0 (2026-02-01) - Initial implementation
  - Async database logging
  - Non-blocking writes
  - Graceful failure handling

Description:
Custom Python logging handler that writes all log messages to the
agent_logs table in the trading database. This enables the consciousness
framework on the US droplet to observe and review trading activity.
"""

import logging
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from queue import Queue
from threading import Thread

logger = logging.getLogger(__name__)


class DatabaseLogHandler(logging.Handler):
    """
    Logging handler that writes to catalyst_intl.agent_logs table.
    
    Features:
    - Non-blocking async writes via background thread
    - Graceful failure (won't break trading if DB write fails)
    - Structured context support
    - Automatic cycle_id and symbol extraction
    
    Usage:
        from db_logger import DatabaseLogHandler, setup_db_logging
        
        # Option 1: Setup helper
        setup_db_logging(db_pool, 'unified_agent')
        
        # Option 2: Manual setup
        handler = DatabaseLogHandler(db_pool, 'unified_agent')
        logging.getLogger().addHandler(handler)
        
        # Log with context
        logger.info("Trade executed", extra={
            'symbol': '0700',
            'context': {'price': 400.50, 'quantity': 100}
        })
    """
    
    def __init__(self, db_pool, source: str, batch_size: int = 10, flush_interval: float = 5.0):
        """
        Initialize DatabaseLogHandler.
        
        Args:
            db_pool: asyncpg connection pool
            source: Source identifier (e.g., 'unified_agent', 'tool_executor')
            batch_size: Number of logs to batch before writing
            flush_interval: Seconds between forced flushes
        """
        super().__init__()
        self.db_pool = db_pool
        self.source = source
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self._queue: Queue = Queue()
        self._running = False
        self._worker: Optional[Thread] = None
        self._cycle_id: Optional[str] = None
        
        # Start background worker
        self.start()
    
    def set_cycle_id(self, cycle_id: str):
        """Set current cycle ID for log correlation."""
        self._cycle_id = cycle_id
    
    def clear_cycle_id(self):
        """Clear cycle ID at end of cycle."""
        self._cycle_id = None
    
    def start(self):
        """Start the background writer thread."""
        if self._worker is not None and self._worker.is_alive():
            return
        
        self._running = True
        self._worker = Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
    
    def stop(self):
        """Stop the background writer thread."""
        self._running = False
        if self._worker:
            self._queue.put(None)  # Signal to stop
            self._worker.join(timeout=5)
            self._worker = None
    
    def emit(self, record: logging.LogRecord):
        """
        Emit a log record to the database queue.
        
        Extracts context from record.extra if present.
        """
        try:
            # Extract extra fields
            symbol = getattr(record, 'symbol', None)
            context = getattr(record, 'context', None)
            error_type = getattr(record, 'error_type', None)
            
            # Build context dict
            ctx = {}
            if context:
                if isinstance(context, dict):
                    ctx = context
                else:
                    ctx['data'] = str(context)
            
            # Add any other extra attributes
            for key in ['tool', 'order_id', 'position_id', 'broker_response']:
                val = getattr(record, key, None)
                if val is not None:
                    ctx[key] = val
            
            # Build log entry
            entry = {
                'timestamp': datetime.now(timezone.utc),
                'level': record.levelname,
                'source': self.source,
                'message': record.getMessage(),
                'context': ctx if ctx else None,
                'cycle_id': self._cycle_id,
                'symbol': symbol,
                'error_type': error_type,
                'stack_trace': self._format_exception(record) if record.exc_info else None
            }
            
            self._queue.put(entry)
            
        except Exception as e:
            # Never break the application due to logging failure
            print(f"DB logging error: {e}")
    
    def _format_exception(self, record: logging.LogRecord) -> Optional[str]:
        """Format exception info as string."""
        if record.exc_info:
            return self.formatter.formatException(record.exc_info) if self.formatter else str(record.exc_info)
        return None
    
    def _worker_loop(self):
        """Background worker that batches and writes logs."""
        batch = []
        last_flush = datetime.now()
        
        while self._running:
            try:
                # Get item with timeout for periodic flush
                try:
                    item = self._queue.get(timeout=1.0)
                except:
                    item = None
                
                if item is None:
                    # Check if we should flush due to timeout
                    if batch and (datetime.now() - last_flush).total_seconds() >= self.flush_interval:
                        self._flush_batch(batch)
                        batch = []
                        last_flush = datetime.now()
                    continue
                
                batch.append(item)
                
                # Flush if batch is full
                if len(batch) >= self.batch_size:
                    self._flush_batch(batch)
                    batch = []
                    last_flush = datetime.now()
                    
            except Exception as e:
                print(f"DB logger worker error: {e}")
        
        # Final flush on shutdown
        if batch:
            self._flush_batch(batch)
    
    def _flush_batch(self, batch: list):
        """Write batch of logs to database."""
        if not batch:
            return
        
        try:
            # Run async insert in new event loop (we're in a thread)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._write_batch(batch))
            finally:
                loop.close()
        except Exception as e:
            print(f"DB batch write error: {e}")
    
    async def _write_batch(self, batch: list):
        """Async batch insert to database."""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.executemany("""
                    INSERT INTO agent_logs 
                    (timestamp, level, source, message, context, cycle_id, symbol, error_type, stack_trace)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """, [
                    (
                        entry['timestamp'],
                        entry['level'],
                        entry['source'],
                        entry['message'],
                        json.dumps(entry['context']) if entry['context'] else None,
                        entry['cycle_id'],
                        entry['symbol'],
                        entry['error_type'],
                        entry['stack_trace']
                    )
                    for entry in batch
                ])
        except Exception as e:
            print(f"DB insert error: {e}")


def setup_db_logging(db_pool, source: str, level: int = logging.INFO) -> DatabaseLogHandler:
    """
    Convenience function to set up database logging.
    
    Args:
        db_pool: asyncpg connection pool
        source: Source identifier
        level: Minimum log level to capture
        
    Returns:
        The DatabaseLogHandler instance
    """
    handler = DatabaseLogHandler(db_pool, source)
    handler.setLevel(level)
    
    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    
    return handler


# Module-level handler reference for cycle_id management
_db_handler: Optional[DatabaseLogHandler] = None


def get_db_handler() -> Optional[DatabaseLogHandler]:
    """Get the current database log handler."""
    global _db_handler
    return _db_handler


def set_db_handler(handler: DatabaseLogHandler):
    """Set the module-level database log handler."""
    global _db_handler
    _db_handler = handler
```

---

## Phase 3: Modify unified_agent.py

### Step 3.1: Remove Consciousness Imports and Class

Find and **REMOVE** the following sections:

```python
# REMOVE: These imports (if present)
from consciousness import ClaudeConsciousness  # REMOVE

# REMOVE: The entire ConsciousnessClient class (~60 lines)
class ConsciousnessClient:
    """Interface to consciousness framework."""
    
    def __init__(self, pool: asyncpg.Pool, agent_id: str):
        self.pool = pool
        self.agent_id = agent_id
    
    async def wake_up(self) -> Dict[str, Any]:
        # ... entire method
    
    async def observe(self, category: str, content: str, metadata: Dict = None):
        # ... entire method
    
    async def sleep(self):
        # ... entire method
    
    # REMOVE ALL OF THIS CLASS
```

### Step 3.2: Remove Research Database Pool

Find and **MODIFY** the DatabasePools class:

```python
# BEFORE:
class DatabasePools:
    def __init__(self, trading_url: str, research_url: str):
        self.trading_url = trading_url
        self.research_url = research_url
        self.trading_pool: Optional[asyncpg.Pool] = None
        self.research_pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        self.trading_pool = await asyncpg.create_pool(
            self.trading_url, min_size=2, max_size=5
        )
        self.research_pool = await asyncpg.create_pool(
            self.research_url, min_size=1, max_size=3
        )

# AFTER:
class DatabasePools:
    def __init__(self, trading_url: str):
        self.trading_url = trading_url
        self.trading_pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        self.trading_pool = await asyncpg.create_pool(
            self.trading_url, min_size=2, max_size=5
        )
        logger.info("Trading database pool created")
    
    async def close(self):
        if self.trading_pool:
            await self.trading_pool.close()
        logger.info("Database pool closed")
```

### Step 3.3: Remove Consciousness Initialization

Find and **REMOVE** consciousness initialization in the agent:

```python
# REMOVE: Consciousness client creation
self.consciousness = ConsciousnessClient(
    self.db.research_pool,
    self.agent_id
)

# REMOVE: Any wake_up calls
await self.consciousness.wake_up()

# REMOVE: Any observe calls
await self.consciousness.observe(...)

# REMOVE: Any sleep calls  
await self.consciousness.sleep()
```

### Step 3.4: Add Database Logging

Add the database logging setup:

```python
# ADD: Import at top of file
from db_logger import DatabaseLogHandler, setup_db_logging, set_db_handler

# ADD: In the agent initialization (after database connection)
async def initialize(self):
    # Connect to database
    self.db = DatabasePools(os.environ['DATABASE_URL'])
    await self.db.connect()
    
    # Setup database logging
    self.db_log_handler = setup_db_logging(
        self.db.trading_pool, 
        'unified_agent',
        level=logging.INFO
    )
    set_db_handler(self.db_log_handler)
    logger.info("Database logging initialized")

# ADD: Set cycle_id at start of each cycle
async def run_cycle(self, mode: str):
    cycle_id = datetime.now().strftime('%Y%m%d-%H%M%S')
    self.db_log_handler.set_cycle_id(cycle_id)
    logger.info(f"Starting cycle {cycle_id} in {mode} mode")
    
    # ... rest of cycle code ...
    
    # Clear cycle_id at end
    self.db_log_handler.clear_cycle_id()
```

### Step 3.5: Update Database URL Loading

```python
# BEFORE:
self.db = DatabasePools(
    os.environ['DATABASE_URL'],
    os.environ['RESEARCH_DATABASE_URL']  # REMOVE THIS
)

# AFTER:
self.db = DatabasePools(os.environ['DATABASE_URL'])
```

---

## Phase 4: Modify tool_executor.py

### Step 4.1: Remove Alert Imports and Usage

```python
# REMOVE: Alert imports
from alerts import AlertSender, create_alert_callback, get_alert_sender

# REMOVE: AlertSender initialization
self.alert_sender = AlertSender()
self.alert_callback = create_alert_callback()

# REMOVE: Alert sending code - replace with logging
# BEFORE:
if self.alert_callback:
    try:
        if hasattr(self.alert_callback, 'send'):
            self.alert_callback.send(
                "info",
                f"Trade Executed: {side.upper()} {symbol}",
                alert_msg
            )

# AFTER:
logger.info(f"Trade executed: {side} {quantity} {symbol} @ {fill_price}", extra={
    'symbol': symbol,
    'context': {
        'side': side,
        'quantity': quantity,
        'price': fill_price,
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'reason': reason
    }
})
```

### Step 4.2: Remove All alert_callback References

Search for and remove all instances of:
- `self.alert_callback`
- `alert_callback=`
- `.send("info",`
- `.send("warning",`
- `.send("critical",`

Replace with appropriate `logger.info()`, `logger.warning()`, or `logger.error()` calls.

---

## Phase 5: Modify position_monitor_service.py

### Step 5.1: Remove Research Database Pool

```python
# REMOVE: Research pool initialization
self.research_pool = await asyncpg.create_pool(
    os.environ.get('RESEARCH_DATABASE_URL'),
    min_size=1, max_size=3
)

# REMOVE: Research pool close
if self.research_pool:
    await self.research_pool.close()
```

### Step 5.2: Remove Consciousness Methods

```python
# REMOVE: Entire consciousness section
# ========================================================================
# CONSCIOUSNESS INTEGRATION
# ========================================================================

async def notify_consciousness(
    self,
    message: str,
    priority: str = 'normal',
    subject: str = 'Position Monitor Alert'
):
    # REMOVE ENTIRE METHOD

async def record_observation(self, content: str, obs_type: str = 'trading'):
    # REMOVE ENTIRE METHOD
```

### Step 5.3: Replace Consciousness Calls with Logging

```python
# BEFORE:
await self.notify_consciousness("Position closed due to stop loss", priority="high")
await self.record_observation("Exit signal detected for 0700", "trading")

# AFTER:
logger.warning("Position closed due to stop loss", extra={
    'symbol': symbol,
    'context': {'reason': 'stop_loss', 'pnl': pnl}
})
logger.info("Exit signal detected", extra={
    'symbol': '0700',
    'context': {'signal_type': 'stop_loss'}
})
```

### Step 5.4: Add Database Logging Setup

```python
# ADD: Import at top
from db_logger import DatabaseLogHandler, setup_db_logging

# ADD: In initialization
async def start(self):
    # Connect to database
    self.db_pool = await asyncpg.create_pool(
        os.environ['DATABASE_URL'],
        min_size=2, max_size=5
    )
    
    # Setup database logging
    self.db_log_handler = setup_db_logging(
        self.db_pool,
        'position_monitor',
        level=logging.INFO
    )
    logger.info("Position monitor started with database logging")
```

---

## Phase 6: Delete Unused Files

### Step 6.1: Remove consciousness.py

```bash
# Check if file exists
ls -la consciousness.py

# Remove if present
rm consciousness.py

# Also check for Conscious/ folder
rm -rf Conscious/
```

### Step 6.2: Remove alerts.py

```bash
# Check if file exists
ls -la alerts.py

# Remove
rm alerts.py
```

---

## Phase 7: Update Configuration Files

### Step 7.1: Update .env

Edit `/root/Catalyst-Trading-System-International/catalyst-international/.env`:

```bash
# REMOVE these lines:
RESEARCH_DATABASE_URL=postgresql://...catalyst_research...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
ALERT_EMAIL=

# KEEP these lines:
DATABASE_URL=postgresql://doadmin:xxx@xxx:25060/catalyst_intl?sslmode=require
ANTHROPIC_API_KEY=sk-ant-xxx
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111
AGENT_ID=intl_claude
LOG_LEVEL=INFO
```

### Step 7.2: Update intl_claude_config.yaml

Edit `/root/Catalyst-Trading-System-International/catalyst-international/config/intl_claude_config.yaml`:

```yaml
# REMOVE this entire section:
# consciousness:
#   enabled: true
#   database: catalyst_research
#   record_observations: true
#   record_learnings: true
#   process_messages: true
#   siblings:
#     - big_bro
#     - dev_claude
#     - public_claude

# KEEP all other sections (agent, market, broker, trading, signals, ai, monitoring)
```

---

## Phase 8: Verification

### Step 8.1: Check for Remaining References

```bash
cd /root/Catalyst-Trading-System-International/catalyst-international

# Search for consciousness references
grep -r "consciousness" *.py
grep -r "RESEARCH_DATABASE" *.py
grep -r "research_pool" *.py

# Search for alert/email references  
grep -r "AlertSender" *.py
grep -r "alert_callback" *.py
grep -r "smtp" *.py --ignore-case
grep -r "send_alert" *.py

# All should return empty (no matches)
```

### Step 8.2: Syntax Check

```bash
cd /root/Catalyst-Trading-System-International/catalyst-international
source venv/bin/activate

# Check each file for syntax errors
python3 -m py_compile unified_agent.py
python3 -m py_compile tool_executor.py
python3 -m py_compile position_monitor_service.py
python3 -m py_compile db_logger.py

echo "All syntax checks passed"
```

### Step 8.3: Test Database Logging

```bash
cd /root/Catalyst-Trading-System-International/catalyst-international
source venv/bin/activate

# Quick test script
python3 << 'EOF'
import asyncio
import asyncpg
import os
import logging
from dotenv import load_dotenv

load_dotenv()

async def test():
    # Connect to database
    pool = await asyncpg.create_pool(os.environ['DATABASE_URL'])
    
    # Test direct insert to agent_logs
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO agent_logs (level, source, message, context)
            VALUES ('INFO', 'test', 'Database logging test', '{"test": true}')
        """)
        
        # Verify
        row = await conn.fetchrow("""
            SELECT * FROM agent_logs WHERE source = 'test' ORDER BY id DESC LIMIT 1
        """)
        print(f"Test log inserted: {row['message']}")
        
        # Cleanup
        await conn.execute("DELETE FROM agent_logs WHERE source = 'test'")
    
    await pool.close()
    print("Database logging test PASSED")

asyncio.run(test())
EOF
```

### Step 8.4: Test Agent Startup

```bash
cd /root/Catalyst-Trading-System-International/catalyst-international
source venv/bin/activate
source .env

# Test heartbeat mode (safest - no trading)
python3 unified_agent.py --mode heartbeat

# Check logs were written to database
psql $DATABASE_URL -c "SELECT timestamp, level, source, message FROM agent_logs ORDER BY timestamp DESC LIMIT 10;"
```

### Step 8.5: Test Position Monitor

```bash
# Check service status
systemctl status position-monitor

# If running, restart to pick up changes
systemctl restart position-monitor

# Check logs
journalctl -u position-monitor -f --no-pager -n 50

# Verify database logs
psql $DATABASE_URL -c "SELECT * FROM agent_logs WHERE source = 'position_monitor' ORDER BY timestamp DESC LIMIT 10;"
```

---

## Phase 9: Final Cleanup

### Step 9.1: Remove Backup Files

```bash
# Remove any .pyc files
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# Remove any editor backup files
find . -name "*.bak" -delete
find . -name "*~" -delete
```

### Step 9.2: Verify File Structure

```bash
cd /root/Catalyst-Trading-System-International/catalyst-international
ls -la

# Should see:
# unified_agent.py
# tool_executor.py
# tools.py
# safety.py
# signals.py
# db_logger.py (NEW)
# position_monitor.py
# position_monitor_service.py
# startup_monitor.py
# brokers/
# data/
# config/
# logs/
# venv/
# .env

# Should NOT see:
# consciousness.py (DELETED)
# alerts.py (DELETED)
# Conscious/ folder (DELETED)
```

---

## Phase 10: Restart Services

### Step 10.1: Restart Position Monitor Service

```bash
# Restart the service
systemctl restart position-monitor

# Verify it's running
systemctl status position-monitor

# Watch logs for errors
journalctl -u position-monitor -f
```

### Step 10.2: Verify Cron Schedule

```bash
# Check cron is set up correctly
crontab -l

# Ensure it references the correct paths and doesn't require RESEARCH_DATABASE_URL
```

---

## Rollback Procedure

If anything goes wrong:

```bash
# Restore from backup
cd /root/Catalyst-Trading-System-International/catalyst-international
cp /root/backups/$(date +%Y%m%d)/*.py .
cp /root/backups/$(date +%Y%m%d)/.env .

# Restart services
systemctl restart position-monitor
```

---

## Summary Checklist

| Task | Status |
|------|--------|
| Backup current files | ☐ |
| Create agent_logs table in catalyst_intl | ☐ |
| Create db_logger.py | ☐ |
| Modify unified_agent.py - remove consciousness | ☐ |
| Modify unified_agent.py - add database logging | ☐ |
| Modify tool_executor.py - remove alerts | ☐ |
| Modify tool_executor.py - add logging | ☐ |
| Modify position_monitor_service.py - remove consciousness | ☐ |
| Modify position_monitor_service.py - add logging | ☐ |
| Delete consciousness.py | ☐ |
| Delete alerts.py | ☐ |
| Update .env - remove RESEARCH_DATABASE_URL, SMTP | ☐ |
| Update config yaml - remove consciousness section | ☐ |
| Verify no remaining references | ☐ |
| Test database logging | ☐ |
| Test agent heartbeat | ☐ |
| Test position monitor | ☐ |
| Restart all services | ☐ |

---

## Post-Implementation Notes

After successful implementation:

1. **US Droplet Consciousness** will need to be configured to:
   - Connect to `catalyst_intl` (read-only)
   - Query `agent_logs` table for error review
   - Create observations based on trading activity

2. **Log Retention**: Consider setting up a cron job to clean old logs:
   ```bash
   # Add to crontab - run weekly
   0 0 * * 0 psql $DATABASE_URL -c "DELETE FROM agent_logs WHERE timestamp < NOW() - INTERVAL '30 days';"
   ```

3. **Web Dashboard**: Will display logs from `agent_logs` table for Craig's review

---

**END OF IMPLEMENTATION GUIDE**

*Version 1.0.0 - February 2026*
*For: Claude Code on International Droplet*
