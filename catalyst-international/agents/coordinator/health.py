"""
BRAIN COMPONENT: Survival Pulse
Biological parallel: Brainstem — heartbeat, breathing, pain response.

This component runs FIRST in every brain cycle. Before the brain can
think about trading, it must know its organs are alive and functioning.

The brain does not trade blind. The brain does not ignore pain.

Version: 1.1.0  (2026-02-28)
  - Replaced check_risk test with get_portfolio (tests trade API directly,
    no params needed, not fooled by sync handler timing)
  - Added get_portfolio degraded context for decision engine
  - Improved _test_tool: log failures, check for empty/null results
"""

import logging
from datetime import datetime

log = logging.getLogger("brain.survival")


class SurvivalPulse:
    """
    Brain component that verifies organ health before every cycle.

    Runs a test call against each critical organ tool via MCP.
    Tracks consecutive failures. Fires pain signals.
    Reports health status to other brain components.
    """

    ORGAN_TESTS = {
        "get_quote": {
            "server": "market-scanner",
            "params": {"symbol": "0700"},
            "critical": True,
        },
        "get_technicals": {
            "server": "market-scanner",
            "params": {"symbol": "0700", "timeframe": "1h"},
            "critical": False,  # Brain can operate degraded without this
        },
        "get_portfolio": {
            "server": "trade-executor",
            "params": {},
            "critical": True,
        },
    }

    # Cerebellum is checked separately (not an MCP organ)
    # The coordinator checks cerebellum.is_loaded() in Layer 1

    PAIN_THRESHOLD = 3
    ORGAN_FAILURE_THRESHOLD = 6

    def __init__(self):
        self.tool_state: dict = {}

    async def pulse(self, hub) -> dict:
        """
        Run the survival check. Returns brain-readable health status.

        This is the FIRST thing the brain does every cycle.
        Nothing else runs if this returns dead=True.
        """
        available = []
        degraded = []
        pain_signals = []

        for tool_name, config in self.ORGAN_TESTS.items():
            alive = await self._test_tool(hub, tool_name, config["server"], config["params"])

            if alive:
                prev_failures = self.tool_state.get(tool_name, {}).get("failures", 0)
                if prev_failures > 0:
                    log.info(f"HEALED: {tool_name} recovered after {prev_failures} failures")

                self.tool_state[tool_name] = {
                    "status": "healthy",
                    "failures": 0,
                    "last_success": datetime.now().isoformat(),
                    "error": None,
                }
                available.append(tool_name)
            else:
                prev = self.tool_state.get(tool_name, {})
                failures = prev.get("failures", 0) + 1

                self.tool_state[tool_name] = {
                    "status": "failed",
                    "failures": failures,
                    "last_success": prev.get("last_success"),
                    "error": prev.get("error", "unknown"),
                    "since": prev.get("since", datetime.now().isoformat()),
                }
                degraded.append(tool_name)

                if failures >= self.ORGAN_FAILURE_THRESHOLD:
                    pain_signals.append({
                        "level": "ORGAN_FAILURE",
                        "tool": tool_name,
                        "organ": config["server"],
                        "failures": failures,
                        "since": self.tool_state[tool_name]["since"],
                        "error": self.tool_state[tool_name]["error"],
                    })
                    log.error(
                        f"ORGAN FAILURE: {config['server']}.{tool_name} "
                        f"-- {failures} consecutive failures"
                    )
                elif failures >= self.PAIN_THRESHOLD:
                    pain_signals.append({
                        "level": "PAIN",
                        "tool": tool_name,
                        "organ": config["server"],
                        "failures": failures,
                        "since": self.tool_state[tool_name]["since"],
                        "error": self.tool_state[tool_name]["error"],
                    })
                    log.warning(
                        f"PAIN: {config['server']}.{tool_name} "
                        f"-- {failures} consecutive failures"
                    )

        critical_down = any(
            tool_name in degraded
            for tool_name, cfg in self.ORGAN_TESTS.items()
            if cfg["critical"]
        )

        score = len(available)
        max_score = len(self.ORGAN_TESTS)

        return {
            "alive": score > 0,
            "dead": score == 0,
            "healthy": score == max_score,
            "degraded": 0 < score < max_score,
            "critical_down": critical_down,
            "score": score,
            "max_score": max_score,
            "available_tools": available,
            "degraded_tools": degraded,
            "pain_signals": pain_signals,
            "tool_state": self.tool_state,
        }

    def get_context_for_decision_engine(self, health: dict) -> str:
        """Translate health status into context the Decision Engine can act on."""
        if health["healthy"]:
            return ""

        if health["dead"]:
            return "ALL ORGANS DOWN. Do not attempt trading. Alert consciousness."

        parts = []

        if health["degraded_tools"]:
            parts.append(
                f"DEGRADED MODE: Broken tools: {', '.join(health['degraded_tools'])}. "
                f"Working tools: {', '.join(health['available_tools'])}."
            )

        if "get_technicals" in health["degraded_tools"]:
            parts.append(
                "RSI, MACD, SMA are UNAVAILABLE. Trade on price action + volume only. "
                "Use Tier 3 sizing. Missing technicals != no trading."
            )

        if "get_quote" in health["degraded_tools"]:
            parts.append(
                "Quote data UNAVAILABLE. Cannot determine prices. Minimal operation only."
            )

        if "get_portfolio" in health["degraded_tools"]:
            parts.append(
                "TRADE API DOWN. Cannot get portfolio, execute trades, or check risk. "
                "Do NOT attempt any trades. Alert consciousness."
            )

        return "\n".join(parts)

    def format_alert(self) -> str:
        """Format pain signals for logging/alerting."""
        healthy = sum(1 for s in self.tool_state.values() if s["status"] == "healthy")
        lines = [f"HEALTH ALERT -- Score: {healthy}/{len(self.tool_state)}"]
        for tool, state in self.tool_state.items():
            if state["failures"] >= self.PAIN_THRESHOLD:
                lines.append(
                    f"  {tool}: {state['failures']} failures "
                    f"since {state.get('since', '?')} -- {state.get('error', '?')}"
                )
        return "\n".join(lines)

    async def _test_tool(self, hub, tool_name: str, server: str, params: dict) -> bool:
        """Test one tool via MCP. Returns True=working, False=broken."""
        try:
            result = await hub.call(server, tool_name, params)

            # Empty or null result = something went wrong
            if not result:
                log.warning(f"PULSE: {server}.{tool_name} returned empty result")
                self.tool_state.setdefault(tool_name, {})["error"] = "empty result"
                return False

            if isinstance(result, dict):
                # Check for explicit error indicators
                if result.get("error") or result.get("success") is False:
                    error_msg = str(result.get("error", "success=False"))[:200]
                    log.warning(f"PULSE: {server}.{tool_name} FAILED: {error_msg}")
                    self.tool_state.setdefault(tool_name, {})["error"] = error_msg
                    return False

                # For get_portfolio: verify we got real data back (cash field present)
                if tool_name == "get_portfolio" and "cash" not in result:
                    error_msg = f"get_portfolio returned unexpected shape: {list(result.keys())[:5]}"
                    log.warning(f"PULSE: {server}.{tool_name} FAILED: {error_msg}")
                    self.tool_state.setdefault(tool_name, {})["error"] = error_msg
                    return False

            log.debug(f"PULSE: {server}.{tool_name} OK")
            return True
        except Exception as e:
            error_msg = str(e)[:200]
            log.warning(f"PULSE: {server}.{tool_name} EXCEPTION: {error_msg}")
            self.tool_state.setdefault(tool_name, {})["error"] = error_msg
            return False
