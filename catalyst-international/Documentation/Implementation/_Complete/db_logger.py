"""
Name of Application: Catalyst Trading System
Name of file: db_logger.py
Version: 1.1.0
Last Updated: 2026-02-01
Purpose: Database logging handler for observability

REVISION HISTORY:
v1.1.0 (2026-02-01) - Addressed implementation concerns
  - Reuse single event loop in worker thread (not new loop per flush)
  - Added fallback file logging when DB unavailable
  - Added queue backpressure with maxsize
  - Added retry logic with exponential backoff
  - Added health tracking for DB connection

v1.0.0 (2026-02-01) - Initial implementation
  - Async database logging
  - Non-blocking writes
  - Graceful failure handling

Description:
Custom Python logging handler that writes all log messages to the
agent_logs table in the trading database. This enables the consciousness
framework on the US droplet to observe and review trading activity.

Features:
- Non-blocking async writes via background thread
- Fallback to file logging when DB unavailable
- Queue backpressure to prevent memory issues
- Retry logic with exponential backoff
- Graceful degradation (never breaks trading)
"""

import logging
import json
import asyncio
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from queue import Queue, Full, Empty
from threading import Thread, Event
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseLogHandler(logging.Handler):
    """
    Logging handler that writes to catalyst_intl.agent_logs table.
    
    Features:
    - Non-blocking async writes via background thread
    - Fallback to file logging when DB unavailable
    - Queue backpressure (maxsize) to prevent memory issues
    - Retry logic with exponential backoff
    - Graceful failure (won't break trading if DB write fails)
    
    Usage:
        from db_logger import DatabaseLogHandler, setup_db_logging
        
        # Option 1: Setup helper
        handler = setup_db_logging(db_pool, 'unified_agent')
        
        # Option 2: Manual setup
        handler = DatabaseLogHandler(db_pool, 'unified_agent')
        logging.getLogger().addHandler(handler)
        
        # Log with context
        logger.info("Trade executed", extra={
            'symbol': '0700',
            'context': {'price': 400.50, 'quantity': 100}
        })
    """
    
    def __init__(
        self, 
        db_pool, 
        source: str, 
        batch_size: int = 10, 
        flush_interval: float = 5.0,
        max_queue_size: int = 1000,
        fallback_log_dir: str = None,
        max_retries: int = 3
    ):
        """
        Initialize DatabaseLogHandler.
        
        Args:
            db_pool: asyncpg connection pool
            source: Source identifier (e.g., 'unified_agent', 'tool_executor')
            batch_size: Number of logs to batch before writing
            flush_interval: Seconds between forced flushes
            max_queue_size: Maximum queue size (backpressure)
            fallback_log_dir: Directory for fallback file logging
            max_retries: Max retries before falling back to file
        """
        super().__init__()
        self.db_pool = db_pool
        self.source = source
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        
        # Queue with backpressure
        self._queue: Queue = Queue(maxsize=max_queue_size)
        self._running = False
        self._worker: Optional[Thread] = None
        self._stop_event = Event()
        self._cycle_id: Optional[str] = None
        
        # Fallback file logging
        if fallback_log_dir:
            self._fallback_dir = Path(fallback_log_dir)
        else:
            self._fallback_dir = Path(os.environ.get('LOG_DIR', '/tmp/catalyst-logs'))
        self._fallback_dir.mkdir(parents=True, exist_ok=True)
        self._fallback_file = self._fallback_dir / f"db_fallback_{source}.log"
        
        # Health tracking
        self._db_healthy = True
        self._consecutive_failures = 0
        self._last_successful_write = None
        
        # Worker thread event loop (reused, not created per flush)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Start background worker
        self.start()
    
    def set_cycle_id(self, cycle_id: str):
        """Set current cycle ID for log correlation."""
        self._cycle_id = cycle_id
    
    def clear_cycle_id(self):
        """Clear cycle ID at end of cycle."""
        self._cycle_id = None
    
    @property
    def is_healthy(self) -> bool:
        """Check if DB logging is healthy."""
        return self._db_healthy
    
    def start(self):
        """Start the background writer thread."""
        if self._worker is not None and self._worker.is_alive():
            return
        
        self._running = True
        self._stop_event.clear()
        self._worker = Thread(target=self._worker_loop, daemon=True, name=f"db_logger_{self.source}")
        self._worker.start()
        logger.debug(f"DatabaseLogHandler started for {self.source}")
    
    def stop(self, timeout: float = 10.0):
        """Stop the background writer thread gracefully."""
        self._running = False
        self._stop_event.set()
        
        if self._worker:
            self._worker.join(timeout=timeout)
            if self._worker.is_alive():
                logger.warning(f"DatabaseLogHandler worker did not stop cleanly for {self.source}")
            self._worker = None
        
        # Close the event loop if we created one
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        logger.debug(f"DatabaseLogHandler stopped for {self.source}")
    
    def emit(self, record: logging.LogRecord):
        """
        Emit a log record to the database queue.
        
        Extracts context from record.extra if present.
        If queue is full, writes directly to fallback file.
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
            
            # Try to add to queue with backpressure handling
            try:
                self._queue.put_nowait(entry)
            except Full:
                # Queue is full - write directly to fallback file
                self._write_to_fallback([entry], reason="queue_full")
                
        except Exception as e:
            # Never break the application due to logging failure
            # Write to stderr as last resort
            print(f"DB logging error in emit(): {e}")
    
    def _format_exception(self, record: logging.LogRecord) -> Optional[str]:
        """Format exception info as string."""
        if record.exc_info:
            try:
                if self.formatter:
                    return self.formatter.formatException(record.exc_info)
                else:
                    import traceback
                    return ''.join(traceback.format_exception(*record.exc_info))
            except Exception:
                return str(record.exc_info)
        return None
    
    def _worker_loop(self):
        """
        Background worker that batches and writes logs.
        
        Uses a single persistent event loop (not created per flush).
        """
        # Create a single event loop for this thread
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        batch: List[Dict] = []
        last_flush = datetime.now()
        
        try:
            while self._running or not self._queue.empty():
                try:
                    # Get item with timeout for periodic flush
                    try:
                        item = self._queue.get(timeout=1.0)
                        if item is not None:
                            batch.append(item)
                    except Empty:
                        pass
                    
                    # Check if we should stop
                    if self._stop_event.is_set() and self._queue.empty():
                        break
                    
                    # Determine if we should flush
                    should_flush = (
                        len(batch) >= self.batch_size or
                        (batch and (datetime.now() - last_flush).total_seconds() >= self.flush_interval) or
                        (self._stop_event.is_set() and batch)  # Flush remaining on shutdown
                    )
                    
                    if should_flush and batch:
                        self._flush_batch_sync(batch)
                        batch = []
                        last_flush = datetime.now()
                        
                except Exception as e:
                    logger.error(f"DB logger worker error: {e}")
                    # Don't lose the batch - write to fallback
                    if batch:
                        self._write_to_fallback(batch, reason="worker_error")
                        batch = []
        finally:
            # Final flush on shutdown
            if batch:
                self._flush_batch_sync(batch)
            
            # Clean up event loop
            try:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception:
                pass
            self._loop.close()
            self._loop = None
    
    def _flush_batch_sync(self, batch: List[Dict]):
        """
        Flush batch synchronously using the worker's event loop.
        
        Includes retry logic with exponential backoff.
        """
        if not batch or not self._loop:
            return
        
        retries = 0
        backoff = 1.0
        
        while retries <= self.max_retries:
            try:
                self._loop.run_until_complete(self._write_batch(batch))
                
                # Success - update health
                self._db_healthy = True
                self._consecutive_failures = 0
                self._last_successful_write = datetime.now()
                return
                
            except Exception as e:
                retries += 1
                self._consecutive_failures += 1
                
                if retries <= self.max_retries:
                    logger.warning(f"DB write failed (attempt {retries}/{self.max_retries}): {e}")
                    # Exponential backoff
                    self._loop.run_until_complete(asyncio.sleep(backoff))
                    backoff *= 2
                else:
                    # Max retries exceeded - fall back to file
                    logger.error(f"DB write failed after {self.max_retries} retries, falling back to file")
                    self._db_healthy = False
                    self._write_to_fallback(batch, reason="db_failure")
    
    async def _write_batch(self, batch: List[Dict]):
        """Async batch insert to database."""
        if not batch:
            return
        
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
    
    def _write_to_fallback(self, batch: List[Dict], reason: str = "unknown"):
        """
        Write logs to fallback file when DB is unavailable.
        
        File format is JSONL (one JSON object per line) for easy parsing.
        """
        try:
            with open(self._fallback_file, 'a') as f:
                for entry in batch:
                    # Add fallback metadata
                    entry['_fallback_reason'] = reason
                    entry['_fallback_at'] = datetime.now(timezone.utc).isoformat()
                    
                    # Convert timestamp to string for JSON
                    if isinstance(entry.get('timestamp'), datetime):
                        entry['timestamp'] = entry['timestamp'].isoformat()
                    
                    f.write(json.dumps(entry) + '\n')
            
            logger.debug(f"Wrote {len(batch)} logs to fallback file: {self._fallback_file}")
            
        except Exception as e:
            # Last resort - print to stderr
            print(f"CRITICAL: Failed to write to fallback file: {e}")
            for entry in batch:
                print(f"LOST LOG: {entry.get('level')} - {entry.get('message')}")


def setup_db_logging(
    db_pool, 
    source: str, 
    level: int = logging.INFO,
    fallback_log_dir: str = None
) -> DatabaseLogHandler:
    """
    Convenience function to set up database logging.
    
    Args:
        db_pool: asyncpg connection pool
        source: Source identifier
        level: Minimum log level to capture
        fallback_log_dir: Directory for fallback logs (default: /tmp/catalyst-logs)
        
    Returns:
        The DatabaseLogHandler instance
    """
    handler = DatabaseLogHandler(
        db_pool, 
        source,
        fallback_log_dir=fallback_log_dir
    )
    handler.setLevel(level)
    
    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    
    # Store reference
    set_db_handler(handler)
    
    logger.info(f"Database logging initialized for {source}")
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


def recover_fallback_logs(db_pool, fallback_file: str) -> int:
    """
    Recover logs from fallback file back to database.
    
    Call this after DB connectivity is restored.
    
    Args:
        db_pool: asyncpg connection pool
        fallback_file: Path to fallback file
        
    Returns:
        Number of logs recovered
    """
    import asyncio
    
    fallback_path = Path(fallback_file)
    if not fallback_path.exists():
        return 0
    
    entries = []
    with open(fallback_path, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                # Remove fallback metadata
                entry.pop('_fallback_reason', None)
                entry.pop('_fallback_at', None)
                # Convert timestamp back
                if isinstance(entry.get('timestamp'), str):
                    entry['timestamp'] = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                entries.append(entry)
            except Exception:
                continue
    
    if not entries:
        return 0
    
    async def write_recovered():
        async with db_pool.acquire() as conn:
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
                    json.dumps(entry['context']) if entry.get('context') else None,
                    entry.get('cycle_id'),
                    entry.get('symbol'),
                    entry.get('error_type'),
                    entry.get('stack_trace')
                )
                for entry in entries
            ])
    
    asyncio.run(write_recovered())
    
    # Rename fallback file to indicate it's been processed
    processed_path = fallback_path.with_suffix('.processed')
    fallback_path.rename(processed_path)
    
    logger.info(f"Recovered {len(entries)} logs from fallback file")
    return len(entries)
