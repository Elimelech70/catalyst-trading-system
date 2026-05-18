"""
Coordinator Agent - The Brain

Continuously running Claude agent that connects to all 3 MCP servers
and orchestrates the trading workflow.

6-Layer Cycle (run in order, every cycle, no layer skipped):
  Layer 1: Heartbeat     - Am I alive? Are organs reachable? Is cerebellum loaded?
  Layer 2: State          - Load identity (CLAUDE.md), learnings, attention mode
  Layer 3: Self-Regulation - Budget, hours, discipline check
  Layer 4: Working Memory - Load CLAUDE-FOCUS.md, signals, positions, neural signals
  Layer 5: Inter-Agent    - Read DIRECTED signals from big_bro, body health
  Layer 6: Voice          - Decision Engine (Claude AI) with full context

Version: 3.0.0 — Full 6-layer cycle per architecture v2.3
"""

import asyncio
import json
import logging
import os
import sys
import time as time_module
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import anthropic
from mcp import ClientSession
from mcp.client.sse import sse_client

from system_prompt import build_system_prompt
from health import SurvivalPulse
from discipline import DisciplineGate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("coordinator")

HK_TZ = ZoneInfo("Asia/Hong_Kong")

# HKEX holiday calendar (non-weekend days when market is closed)
# Source: Moomoo request_trading_days API, verified April 2026
# Update this at the start of each year
HKEX_HOLIDAYS_2026 = {
    "2026-01-01",  # New Year's Day
    "2026-02-17",  # Lunar New Year
    "2026-02-18",  # Lunar New Year
    "2026-02-19",  # Lunar New Year
    "2026-04-03",  # Ching Ming Festival
    "2026-04-06",  # Easter Monday
    "2026-04-07",  # Day after Easter Monday
    "2026-05-01",  # Labour Day
    "2026-05-25",  # Buddha's Birthday
    "2026-06-19",  # Tuen Ng Festival
    "2026-07-01",  # HKSAR Establishment Day
    "2026-10-01",  # National Day
    "2026-10-19",  # Chung Yeung Festival
    "2026-12-25",  # Christmas Day
}
# Half days (morning session only, close at 12:00)
HKEX_HALF_DAYS_2026 = {
    "2026-12-24",  # Christmas Eve
    "2026-12-31",  # New Year's Eve
}

# Configuration
POLL_INTERVAL = 60  # seconds between recommendation checks
SCAN_INTERVAL = 1800  # 30 minutes between full scan cycles
MAX_ITERATIONS_PER_CYCLE = 35
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
MAX_TOKENS = 4096


# ============================================================================
# MCP Client Connections
# ============================================================================

class MCPConnection:
    """Manages connection to a single MCP server with auto-reconnect."""

    MAX_RECONNECT_ATTEMPTS = 3
    RECONNECT_DELAY = 5  # seconds

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.session: Optional[ClientSession] = None
        self._read_stream = None
        self._write_stream = None
        self._context = None
        self._connected = False

    async def connect(self):
        """Connect to the MCP server."""
        logger.info(f"Connecting to {self.name} at {self.url}")
        self._context = sse_client(self.url)
        streams = await self._context.__aenter__()
        self._read_stream, self._write_stream = streams
        self.session = ClientSession(self._read_stream, self._write_stream)
        await self.session.__aenter__()
        await self.session.initialize()
        tools = await self.session.list_tools()
        tool_names = [t.name for t in tools.tools]
        self._connected = True
        logger.info(f"Connected to {self.name}: tools={tool_names}")

    async def disconnect(self):
        self._connected = False
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            if self._context:
                await self._context.__aexit__(None, None, None)
        except Exception:
            pass
        self.session = None
        self._context = None
        logger.info(f"Disconnected from {self.name}")

    async def reconnect(self):
        """Disconnect and reconnect to the MCP server."""
        logger.warning(f"Reconnecting to {self.name}...")
        await self.disconnect()
        await self.connect()

    async def call_tool(self, tool_name: str, arguments: dict = None) -> Any:
        """Call a tool on this MCP server, with auto-reconnect on failure."""
        last_error = None
        for attempt in range(self.MAX_RECONNECT_ATTEMPTS):
            if not self._connected or not self.session:
                try:
                    await self.reconnect()
                except Exception as e:
                    last_error = e
                    logger.warning(f"Reconnect to {self.name} failed (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(self.RECONNECT_DELAY)
                    continue

            try:
                result = await self.session.call_tool(tool_name, arguments or {})
                # Extract text content
                if result.content and len(result.content) > 0:
                    text = result.content[0].text
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {"raw": text}
                return {}
            except Exception as e:
                last_error = e
                logger.warning(f"Tool call {self.name}.{tool_name} failed (attempt {attempt + 1}): {e}")
                self._connected = False
                if attempt < self.MAX_RECONNECT_ATTEMPTS - 1:
                    await asyncio.sleep(self.RECONNECT_DELAY)

        raise RuntimeError(f"Failed to call {self.name}.{tool_name} after {self.MAX_RECONNECT_ATTEMPTS} attempts: {last_error}")


class MCPHub:
    """Manages connections to all MCP servers."""

    def __init__(self, config: dict):
        self.connections: Dict[str, MCPConnection] = {}
        for name, server_config in config.get("mcpServers", {}).items():
            self.connections[name] = MCPConnection(name, server_config["url"])

    async def connect_all(self):
        for conn in self.connections.values():
            try:
                await conn.connect()
            except Exception as e:
                logger.error(f"Failed to connect to {conn.name}: {e}")

    async def disconnect_all(self):
        for conn in self.connections.values():
            try:
                await conn.disconnect()
            except Exception:
                pass

    def get(self, name: str) -> MCPConnection:
        conn = self.connections.get(name)
        if not conn:
            raise KeyError(f"No MCP server named '{name}'")
        return conn

    async def call(self, server_name: str, tool_name: str, arguments: dict = None) -> Any:
        """Call a tool on a named MCP server."""
        return await self.get(server_name).call_tool(tool_name, arguments)


# ============================================================================
# Tool adapter for Claude API
# ============================================================================

def build_tool_map() -> Dict[str, tuple]:
    """Maps Claude tool names -> (mcp_server, mcp_tool_name)."""
    return {
        # Position Monitor
        "get_exit_recommendations": ("position-monitor", "get_exit_recommendations"),
        "get_position_health": ("position-monitor", "get_position_health"),
        "acknowledge_recommendation": ("position-monitor", "acknowledge_recommendation"),
        # Market Scanner
        "scan_market": ("market-scanner", "scan_market"),
        "get_quote": ("market-scanner", "get_quote"),
        "get_technicals": ("market-scanner", "get_technicals"),
        "detect_patterns": ("market-scanner", "detect_patterns"),
        "get_news": ("market-scanner", "get_news"),
        # Trade Executor
        "get_portfolio": ("trade-executor", "get_portfolio"),
        "execute_trade": ("trade-executor", "execute_trade"),
        "close_position": ("trade-executor", "close_position"),
        "close_all": ("trade-executor", "close_all"),
        "sync_positions": ("trade-executor", "sync_positions"),
        "check_risk": ("trade-executor", "check_risk"),
        "log_decision": ("trade-executor", "log_decision"),
        "get_last_trade_date": ("trade-executor", "get_last_trade_date"),
        "publish_signal": ("trade-executor", "publish_signal"),
        "get_signals": ("trade-executor", "get_signals"),
    }


# ============================================================================
# Coordinator
# ============================================================================

class Coordinator:
    """
    The Brain. Composed of components:
      - Survival Pulse (brainstem)
      - Discipline Gate (limbic)
      - Decision Engine (prefrontal cortex / Claude AI)
    """

    # Paths for memory files (mounted as volumes or local)
    MEMORY_PATHS = [
        "/app/memory",       # Docker volume mount
        "/app",              # Fallback in container
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),  # Dev: repo root
    ]

    def __init__(self, mcp_config: dict):
        self.hub = MCPHub(mcp_config)
        self.anthropic = anthropic.Anthropic()
        self.running = True
        self.last_scan_time: Optional[datetime] = None

        # Tool routing map
        self._tool_map = build_tool_map()

        # Brain components
        self.survival = SurvivalPulse()
        self.discipline = DisciplineGate()

        # Attention state (Layer 2) — full state machine in Phase 2
        self.attention_mode = "SECURITY_SELECTION"

    # ------------------------------------------------------------------
    # Memory loading (Layer 2 + Layer 4)
    # ------------------------------------------------------------------

    def _find_memory_file(self, filename: str) -> Optional[str]:
        """Search known paths for a memory file."""
        for base in self.MEMORY_PATHS:
            path = os.path.join(base, filename)
            if os.path.isfile(path):
                return path
        return None

    def _load_memory_file(self, filename: str, max_lines: int = 0) -> str:
        """Load a memory file. Returns empty string if not found."""
        path = self._find_memory_file(filename)
        if not path:
            logger.debug(f"Memory file not found: {filename}")
            return ""
        try:
            with open(path, "r") as f:
                content = f.read()
            if max_lines > 0:
                lines = content.split("\n")
                content = "\n".join(lines[:max_lines])
            logger.info(f"Loaded memory: {filename} ({len(content)} chars)")
            return content.strip()
        except Exception as e:
            logger.warning(f"Failed to load {filename}: {e}")
            return ""

    def _load_learnings(self) -> str:
        """Layer 2: Load CLAUDE-LEARNINGS.md (medium-term memory)."""
        return self._load_memory_file("CLAUDE-LEARNINGS.md")

    def _load_focus(self) -> str:
        """Layer 4: Load CLAUDE-FOCUS.md (short-term/working memory)."""
        return self._load_memory_file("CLAUDE-FOCUS.md")

    async def _load_signals(self, limit: int = 15) -> str:
        """Layer 4: Load recent signals from the signal bus."""
        try:
            result = await self.hub.call("trade-executor", "get_signals", {"limit": limit})
            signals = result.get("signals", [])
            if not signals:
                return ""
            lines = []
            for sig in signals:
                lines.append(
                    f"- [{sig.get('severity')}] {sig.get('domain')}/{sig.get('scope')}: "
                    f"{sig.get('content', '')[:120]}"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Failed to load signals: {e}")
            return ""

    async def _load_directed_signals(self) -> str:
        """Layer 5: Load DIRECTED:coordinator signals from big_bro."""
        try:
            result = await self.hub.call("trade-executor", "get_signals", {"limit": 10})
            signals = result.get("signals", [])
            directed = [
                s for s in signals
                if "DIRECTED" in s.get("scope", "") and "coordinator" in s.get("scope", "").lower()
            ]
            if not directed:
                return ""
            lines = []
            for sig in directed:
                lines.append(
                    f"- [{sig.get('severity')}] {sig.get('source', 'big_bro')}: "
                    f"{sig.get('content', '')}"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Failed to load directed signals: {e}")
            return ""

    async def start(self):
        """Start the coordinator."""
        logger.info("=" * 60)
        logger.info("BRAIN STARTING - Coordinator v2.0.0")
        logger.info(f"Model: {MODEL}")
        logger.info("Components: Survival Pulse, Discipline Gate, Decision Engine")
        logger.info("=" * 60)

        await self.hub.connect_all()

        # Initial sync
        try:
            sync_result = await self.hub.call("trade-executor", "sync_positions")
            logger.info(f"Initial sync: {sync_result}")
        except Exception as e:
            logger.warning(f"Initial sync failed: {e}")

    async def stop(self):
        """Stop the coordinator."""
        self.running = False
        await self.hub.disconnect_all()
        logger.info("Coordinator stopped")

    def _is_market_open(self) -> bool:
        if os.environ.get("FORCE_MARKET_OPEN"):
            return True
        now = datetime.now(HK_TZ)
        if now.weekday() >= 5:
            return False
        today_str = now.strftime("%Y-%m-%d")
        if today_str in HKEX_HOLIDAYS_2026:
            return False
        ct = now.time()
        if today_str in HKEX_HALF_DAYS_2026:
            # Half day: morning session only
            return time(9, 30) <= ct < time(12, 0)
        if time(9, 30) <= ct < time(12, 0):
            return True
        if time(13, 0) <= ct < time(16, 0):
            return True
        return False

    def _should_run_scan(self) -> bool:
        """Check if it's time for a full scan cycle."""
        if self.last_scan_time is None:
            return True
        elapsed = (datetime.now(HK_TZ) - self.last_scan_time).total_seconds()
        return elapsed >= SCAN_INTERVAL

    # ----- Recommendation handling -----

    async def _handle_recommendations(self):
        """Check for and act on exit recommendations."""
        try:
            recs = await self.hub.call("position-monitor", "get_exit_recommendations")
        except Exception as e:
            logger.warning(f"Failed to get recommendations: {e}")
            return

        count = recs.get("count", 0)
        if count == 0:
            return

        logger.info(f"Processing {count} exit recommendations")

        for rec in recs.get("recommendations", []):
            symbol = rec["symbol"]
            recommendation = rec["recommendation"]
            reason = rec.get("reason", "")
            monitor_id = rec["monitor_id"]

            logger.info(f"  {symbol}: {recommendation} - {reason}")

            action_taken = "held"

            if recommendation == "EXIT":
                try:
                    result = await self.hub.call("trade-executor", "close_position", {
                        "symbol": symbol,
                        "reason": f"Monitor EXIT: {reason}",
                        "exit_type": "AI_PATTERN",
                    })
                    if result.get("success"):
                        action_taken = "closed"
                        logger.info(f"  Closed {symbol}: {result}")
                    else:
                        logger.warning(f"  Close failed for {symbol}: {result}")
                        action_taken = "close_failed"
                except Exception as e:
                    logger.error(f"  Error closing {symbol}: {e}")
                    action_taken = "error"

            elif recommendation == "CONSULT_AI":
                action_taken = await self._consult_on_position(rec)

            try:
                await self.hub.call("position-monitor", "acknowledge_recommendation", {
                    "monitor_id": monitor_id,
                    "action_taken": action_taken,
                })
            except Exception as e:
                logger.warning(f"Failed to acknowledge {monitor_id}: {e}")

    async def _consult_on_position(self, rec: dict) -> str:
        """Use Claude to decide on a CONSULT_AI recommendation."""
        symbol = rec["symbol"]

        try:
            quote_data = await self.hub.call("market-scanner", "get_quote", {"symbol": symbol})
            tech_data = await self.hub.call("market-scanner", "get_technicals", {"symbol": symbol})
        except Exception as e:
            logger.warning(f"Failed to get data for {symbol}: {e}")
            return "held"

        prompt = f"""A position monitor flagged {symbol} for review.

POSITION:
- Entry price: HKD {rec.get('entry_price', '?')}
- Quantity: {rec.get('quantity', '?')}
- Side: {rec.get('side', '?')}

MONITOR REASON: {rec.get('reason', 'Unknown')}

CURRENT QUOTE: {json.dumps(quote_data.get('quote', {}), default=str)}
TECHNICALS: {json.dumps(tech_data.get('technicals', {}), default=str)}

Should I CLOSE this position or HOLD? Reply with just CLOSE or HOLD on the first line, then a brief reason."""

        try:
            response = self.anthropic.messages.create(
                model=MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            first_line = text.split("\n")[0].upper()

            if "CLOSE" in first_line:
                result = await self.hub.call("trade-executor", "close_position", {
                    "symbol": symbol,
                    "reason": f"AI consultation: {text[:100]}",
                    "exit_type": "AI_PATTERN",
                })
                logger.info(f"  AI decided CLOSE for {symbol}: {text[:80]}")
                return "closed"
            else:
                logger.info(f"  AI decided HOLD for {symbol}: {text[:80]}")
                return "held"
        except Exception as e:
            logger.error(f"AI consultation failed: {e}")
            return "held"

    # ----- Brain component: get portfolio for discipline -----

    async def _get_portfolio(self) -> dict:
        """Get portfolio data from trade-executor."""
        try:
            return await self.hub.call("trade-executor", "get_portfolio")
        except Exception as e:
            logger.error(f"Failed to get portfolio: {e}")
            return {"cash": 0, "equity": 0, "position_count": 0, "max_positions": 15}

    async def _publish_signal(self, severity: str, domain: str, scope: str, content: str):
        """Publish a signal to the nervous system via trade-executor."""
        try:
            await self.hub.call("trade-executor", "publish_signal", {
                "severity": severity,
                "domain": domain,
                "scope": scope,
                "content": content,
            })
        except Exception as e:
            logger.warning(f"Failed to publish signal: {e}")

    async def _get_last_trade_date(self) -> Optional[datetime]:
        """Get last trade date from trade-executor for discipline checking."""
        try:
            result = await self.hub.call("trade-executor", "get_last_trade_date")
            date_str = result.get("last_trade_date")
            if date_str:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception as e:
            logger.warning(f"Failed to get last trade date: {e}")
        return None

    # ----- Full scan cycle with brain components -----

    async def _run_scan_cycle(self):
        """
        One brain cycle. 6 layers execute in order. No layer is skipped.
        The output of each layer feeds the next.
        """
        self.last_scan_time = datetime.now(HK_TZ)
        logger.info("=" * 60)
        logger.info(f"BRAIN CYCLE - {self.last_scan_time.strftime('%H:%M:%S %Z')}")
        logger.info("=" * 60)

        # ==============================================================
        # LAYER 1: HEARTBEAT (Brainstem)
        # Am I alive? Are organs reachable? Is cerebellum loaded?
        # ==============================================================
        logger.info("LAYER 1: Heartbeat...")
        health = await self.survival.pulse(self.hub)

        logger.info(
            f"LAYER 1: Score {health['score']}/{health['max_score']}, "
            f"{'healthy' if health['healthy'] else 'DEGRADED' if health['degraded'] else 'DEAD'}"
        )

        if health["dead"]:
            logger.error("LAYER 1: All organs down. Cannot operate. Sleeping.")
            logger.error(self.survival.format_alert())
            return {"tools_called": 0, "trades_executed": 0, "status": "dead"}

        health_context = self.survival.get_context_for_decision_engine(health)

        # Check cerebellum health (Phase 6 integration point)
        cerebellum_context = ""
        try:
            from cerebellum import Cerebellum
            cerebellum = Cerebellum()
            if cerebellum.is_loaded():
                logger.info("LAYER 1: Cerebellum loaded and ready")
            else:
                logger.info("LAYER 1: Cerebellum not loaded — LLM-only mode")
                cerebellum = None
        except ImportError:
            logger.debug("LAYER 1: Cerebellum module not available — LLM-only mode")
            cerebellum = None

        if health["pain_signals"]:
            logger.warning(self.survival.format_alert())
            await self._publish_signal(
                "CRITICAL" if health["dead"] else "WARNING",
                "HEALTH", "BROADCAST",
                self.survival.format_alert(),
            )

        # ==============================================================
        # LAYER 2: STATE (Identity + Formation)
        # Load identity. Load learnings. What mode? What attention state?
        # ==============================================================
        logger.info("LAYER 2: State — loading identity and memory...")
        learnings_content = self._load_learnings()
        logger.info(f"LAYER 2: Attention mode = {self.attention_mode}")

        # ==============================================================
        # LAYER 3: SELF-REGULATION (Limbic system)
        # Budget, hours, discipline. Should I be active?
        # ==============================================================
        logger.info("LAYER 3: Self-Regulation...")
        portfolio = await self._get_portfolio()
        last_trade = await self._get_last_trade_date()

        discipline = self.discipline.check(
            cash=portfolio.get("cash", 0),
            total_capital=portfolio.get("equity", 0) or portfolio.get("cash", 0),
            open_positions=portfolio.get("position_count", 0),
            max_positions=portfolio.get("max_positions", 15),
            last_trade_time=last_trade,
        )

        discipline_context = discipline["context_for_decision_engine"]

        logger.info(
            f"LAYER 3: Discipline -- {discipline['level']}, "
            f"{discipline['days_idle']}d idle, "
            f"{discipline['capital_utilisation']:.1%} deployed, "
            f"{discipline['consecutive_passes']} consecutive passes"
        )

        if discipline["level"] in ("ALARM", "WARNING"):
            logger.warning(self.discipline.format_alert(discipline))
            await self._publish_signal(
                "CRITICAL" if discipline["level"] == "ALARM" else "WARNING",
                "TRADING", "BROADCAST",
                self.discipline.format_alert(discipline),
            )

        # ==============================================================
        # LAYER 4: WORKING MEMORY (Hippocampus)
        # Load CLAUDE-FOCUS.md, recent signals, open positions, neural signals
        # ==============================================================
        logger.info("LAYER 4: Working Memory...")
        focus_content = self._load_focus()
        signals_context = await self._load_signals()

        # Neural signals from cerebellum (Phase 6 integration)
        neural_context = ""
        if cerebellum and cerebellum.is_loaded():
            try:
                neural_context = "Cerebellum active. Neural signals available in tool results."
                logger.info("LAYER 4: Neural signals loaded from cerebellum")
            except Exception as e:
                logger.warning(f"LAYER 4: Failed to load neural signals: {e}")

        if signals_context:
            logger.info(f"LAYER 4: {signals_context.count(chr(10)) + 1} signals loaded")
        if focus_content:
            logger.info(f"LAYER 4: CLAUDE-FOCUS.md loaded ({len(focus_content)} chars)")

        # ==============================================================
        # LAYER 5: INTER-AGENT (Thalamus)
        # Read DIRECTED signals from big_bro. Body health check.
        # ==============================================================
        logger.info("LAYER 5: Inter-Agent...")
        directed_signals = await self._load_directed_signals()
        if directed_signals:
            logger.info(f"LAYER 5: big_bro directives received:\n{directed_signals}")
        else:
            logger.info("LAYER 5: No big_bro directives")

        # ==============================================================
        # LAYER 6: VOICE (Prefrontal cortex)
        # Build full context. Call Decision Engine. Process response.
        # ==============================================================
        logger.info("LAYER 6: Voice — Decision Engine...")

        # Build system prompt with all 6 layers of context
        system_prompt = build_system_prompt(
            health_context=health_context,
            discipline_context=discipline_context,
            degraded_mode=health["degraded"],
            available_tools=health["available_tools"],
            learnings_content=learnings_content,
            focus_content=focus_content,
            signals_context=signals_context,
            directed_signals=directed_signals,
            neural_context=neural_context,
        )

        context = f"""## Trading Cycle Context

**Date/Time**: {datetime.now(HK_TZ).strftime('%Y-%m-%d %H:%M:%S')} HKT
**Mode**: Paper Trading (Multi-Agent MCP Architecture)
**Health**: {health['score']}/{health['max_score']} organs functional
**Discipline**: {discipline['level']} ({discipline['days_idle']}d idle, {discipline['capital_utilisation']:.1%} deployed)

## Your Task
Execute your trading strategy for this cycle:
1. Check current portfolio (get_portfolio)
2. Scan for new opportunities (scan_market)
3. Analyze top candidates (get_quote, get_technicals, detect_patterns, get_news)
4. Execute trades if criteria met (check_risk -> execute_trade)
5. Log all decisions (log_decision)

Begin by checking portfolio, then scan the market."""

        messages = [{"role": "user", "content": context}]
        tools_called = 0
        trades_executed = 0

        # Import tool schemas from tools.py
        try:
            sys.path.insert(0, "/app")
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from tools import TOOLS
        except ImportError:
            logger.warning("Could not import TOOLS from tools.py, using empty tools")
            TOOLS = []

        # Filter tools based on health status
        active_tools = self._filter_tools_by_health(TOOLS, health)

        try:
            for iteration in range(MAX_ITERATIONS_PER_CYCLE):
                logger.info(f"Iteration {iteration + 1}/{MAX_ITERATIONS_PER_CYCLE}")

                response = self.anthropic.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=system_prompt,
                    tools=active_tools,
                    messages=messages,
                )

                messages.append({"role": "assistant", "content": response.content})

                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                if not tool_use_blocks:
                    for block in response.content:
                        if hasattr(block, "text"):
                            logger.info(f"Claude final: {block.text[:200]}")
                    break

                tool_results = []
                for tool_block in tool_use_blocks:
                    tool_name = tool_block.name
                    tool_input = tool_block.input
                    tools_called += 1

                    logger.info(f"  Tool: {tool_name}({json.dumps(tool_input)[:100]})")

                    # Route through MCP
                    if tool_name == "send_alert":
                        logger.info(f"ALERT [{tool_input.get('severity', 'info')}]: {tool_input.get('subject', '')} - {tool_input.get('message', '')}")
                        result = {"sent": True, "success": True}
                    else:
                        server_name, mcp_tool = self._tool_map.get(tool_name, (None, None))
                        if server_name:
                            try:
                                result = await self.hub.call(server_name, mcp_tool, tool_input)
                            except Exception as e:
                                result = {"error": str(e), "success": False}
                        else:
                            result = {"error": f"Unknown tool: {tool_name}", "success": False}

                    # Track trades
                    if tool_name == "execute_trade" and result.get("success"):
                        trades_executed += 1
                        self.discipline.record_trade()

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": json.dumps(result, default=str),
                    })

                messages.append({"role": "user", "content": tool_results})

                if response.stop_reason == "end_turn":
                    break

        except Exception as e:
            logger.error(f"Scan cycle error: {e}", exc_info=True)

        # Record pass/trade for discipline tracking
        if trades_executed == 0:
            self.discipline.record_pass()

        logger.info(f"BRAIN CYCLE COMPLETE: {tools_called} tools, {trades_executed} trades")
        return {"tools_called": tools_called, "trades_executed": trades_executed}

    def _filter_tools_by_health(self, tools: list, health: dict) -> list:
        """
        Only give the Decision Engine tools whose underlying organ is working.
        Don't hand the brain broken instruments.
        """
        if health["healthy"] or not tools:
            return tools

        # Map tool names to the health-checked dependency
        tool_health_map = {
            "scan_market": "get_quote",
            "get_quote": "get_quote",
            "get_technicals": "get_technicals",
            "detect_patterns": "get_technicals",
            "get_news": None,  # Always available
            "execute_trade": "check_risk",
            "check_risk": "check_risk",
            "get_portfolio": None,
            "close_position": None,
            "close_all": None,
            "get_exit_recommendations": None,
            "get_position_health": None,
            "acknowledge_recommendation": None,
            "sync_positions": None,
            "log_decision": None,
            "send_alert": None,
        }

        available = health["available_tools"]
        filtered = []
        for tool in tools:
            tool_name = tool.get("name", "")
            dep = tool_health_map.get(tool_name)
            if dep is None or dep in available:
                filtered.append(tool)
            else:
                logger.info(f"BRAIN: Withholding tool '{tool_name}' -- dependency '{dep}' is broken")

        return filtered

    # ----- Main loop -----

    async def run(self):
        """Main coordinator loop."""
        await self.start()

        while self.running:
            try:
                if not self._is_market_open():
                    now = datetime.now(HK_TZ)
                    logger.info(f"Market closed ({now.strftime('%H:%M')} HKT). Sleeping...")
                    await asyncio.sleep(300)
                    continue

                # Priority 1: Handle exit recommendations
                await self._handle_recommendations()

                # Priority 2: Run scan cycle if due
                if self._should_run_scan():
                    await self._run_scan_cycle()

                # Sleep between polls
                await asyncio.sleep(POLL_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Coordinator loop error: {e}", exc_info=True)
                await asyncio.sleep(60)

        await self.stop()


# ============================================================================
# Entry point
# ============================================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Coordinator Agent")
    parser.add_argument("--force", action="store_true", help="Run even if market closed")
    parser.add_argument("--once", action="store_true", help="Run one cycle then exit")
    args = parser.parse_args()

    if args.force:
        os.environ["FORCE_MARKET_OPEN"] = "1"

    # Load MCP config
    config_paths = [
        "mcp_config.json",
        "agents/coordinator/mcp_config.json",
        os.path.join(os.path.dirname(__file__), "mcp_config.json"),
    ]
    config = None
    for path in config_paths:
        try:
            with open(path) as f:
                config = json.load(f)
                break
        except FileNotFoundError:
            continue

    if not config:
        logger.error("mcp_config.json not found")
        sys.exit(1)

    coordinator = Coordinator(config)

    if args.once:
        await coordinator.start()
        await coordinator._handle_recommendations()
        await coordinator._run_scan_cycle()
        await coordinator.stop()
    else:
        await coordinator.run()


if __name__ == "__main__":
    asyncio.run(main())
