"""
Name of Application: Catalyst Trading System
Name of file: models.py
Version: 3.0.0
Last Updated: 2026-04-08
Purpose: Shared enums and dataclasses for agent body components

REVISION HISTORY:
v3.0.0 (2026-04-08) - v2.4 architecture alignment
- Added COORDINATOR component and tool agent components
- Added AttentionMode (SECURITY_SELECTION, CANDLE_EXECUTION)
- Added CoordinatorLayer enum (6-layer cycle)
- Added ExitType enum (AI_PATTERN, STOP_LOSS, MANUAL, ADVERSARIAL_EVENT)
- Added BrokerType enum (ALPACA, MOOMOO)
- Added StandardOHLCV and TradeFeedback dataclasses
- Added ATTENTION and EXECUTION signal domains
v2.0.0 (2026-04-06) - v8 architecture alignment
- Added Monitor component, Severity/SignalDomain/SignalScope enums
- Added SignalMessage dataclass for 3D signal bus
v1.0.0 (2026-03-03) - Initial creation
- Component, MessageType, Priority, Domain, PFCMode enums
- CommunicationMessage dataclass

Description:
Defines the shared vocabulary for inter-component communication.
All components import these to ensure consistent message types.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


class Component(str, Enum):
    """Brain components that communicate via the nervous system."""
    PFC = "pfc"
    COORDINATOR = "coordinator"
    OCCIPITAL = "occipital"
    CEREBELLUM = "cerebellum"
    HIPPOCAMPUS = "hippocampus"
    MONITOR = "monitor"
    NEURAL = "neural"
    BROADCAST = "broadcast"
    TOOL_POSITION_MONITOR = "tool_position_monitor"
    TOOL_STOP_LOSS = "tool_stop_loss"
    TOOL_RISK_AGGREGATOR = "tool_risk_aggregator"


class MessageType(str, Enum):
    """Types of messages on the communication table."""
    TASK = "task"
    RESULT = "result"
    SIGNAL = "signal"
    STATUS = "status"
    ESCALATION = "escalation"


class Direction(str, Enum):
    """Signal direction on the nervous system."""
    DESCENDING = "descending"  # Coordinator to components (task/intent)
    ASCENDING = "ascending"    # Components to coordinator (result/perception)


class Severity(str, Enum):
    """Signal severity -- v8 architecture 3D identifier dimension 1."""
    CRITICAL = "CRITICAL"   # Adrenaline flood -- processed before all others
    WARNING = "WARNING"     # Attention needed
    INFO = "INFO"           # Normal reporting
    OBSERVE = "OBSERVE"     # Low-priority observation


class SignalDomain(str, Enum):
    """Signal domain -- v8 architecture 3D identifier dimension 2."""
    HEALTH = "HEALTH"         # Component health / liveness
    TRADING = "TRADING"       # Trade execution events
    RISK = "RISK"             # Risk alerts and limits
    LEARNING = "LEARNING"     # Pattern/learning events
    DIRECTION = "DIRECTION"   # big_bro directives
    LIFECYCLE = "LIFECYCLE"   # Start/stop/mode changes
    ATTENTION = "ATTENTION"   # Attention state machine mode changes
    EXECUTION = "EXECUTION"   # Candle execution path events


class SignalScope(str, Enum):
    """Signal scope -- v8 architecture 3D identifier dimension 3."""
    BROADCAST = "BROADCAST"   # All components read

    @staticmethod
    def directed(target: str) -> str:
        """Create a DIRECTED scope for a specific target."""
        return f"DIRECTED:{target}"


class PFCMode(str, Enum):
    """PFC operating modes -- what the whole body is configured for."""
    SLEEPING = "sleeping"
    WAKING = "waking"
    LEARNING = "learning"
    EXECUTING = "executing"
    PONDERING = "pondering"
    RELAXING = "relaxing"
    EMERGENCY = "emergency"


class AttentionMode(str, Enum):
    """Coordinator attention state machine modes -- v2.4 architecture."""
    SECURITY_SELECTION = "security_selection"  # Mode 1: News-to-Security model
    CANDLE_EXECUTION = "candle_execution"      # Mode 2: Candle model


class CoordinatorLayer(str, Enum):
    """The 6-layer coordinator cycle -- no layer is skipped."""
    HEARTBEAT = "heartbeat"              # Layer 1: Am I alive?
    STATE = "state"                      # Layer 2: Identity + mode
    SELF_REGULATION = "self_regulation"  # Layer 3: Budget, hours, limits
    WORKING_MEMORY = "working_memory"    # Layer 4: Load context + neural signals
    INTER_AGENT = "inter_agent"          # Layer 5: big_bro directives, body health
    VOICE = "voice"                      # Layer 6: Attention State Machine


class ExitType(str, Enum):
    """How a trade was exited -- critical for feedback loop."""
    AI_PATTERN = "AI_PATTERN"                    # Position Monitor exited on pattern signal
    STOP_LOSS = "STOP_LOSS"                      # Stop Loss Enforcer brute-force exit
    MANUAL = "MANUAL"                            # Manual close
    ADVERSARIAL_EVENT = "ADVERSARIAL_EVENT"      # Flagged as manufactured move


class BrokerType(str, Enum):
    """Supported broker types for multi-deployment."""
    ALPACA = "alpaca"    # US: NYSE, NASDAQ
    MOOMOO = "moomoo"    # Intl: HKEX


@dataclass
class StandardOHLCV:
    """
    Broker-agnostic candle format -- v2.4 architecture.
    All broker data is normalised to this before reaching the cerebellum/ONNX models.
    """
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str  # '1m' | '5m' | '15m' | '1h' | '1d'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'timeframe': self.timeframe,
        }


@dataclass
class TradeFeedback:
    """
    Per-trade feedback record for the learning loop -- v2.4 architecture.
    Captures exit type and candle context for retraining.
    """
    symbol: str
    market: str                           # US | HKEX
    entry_price: float
    exit_price: float
    return_pct: float
    exit_type: str                        # AI_PATTERN | STOP_LOSS | MANUAL
    pattern_type: Optional[str] = None
    neural_prediction: Optional[str] = None  # JSON: what model predicted at entry
    neural_confidence: Optional[float] = None
    candles_at_exit: Optional[str] = None    # JSON: candle sequence for retraining
    holding_minutes: Optional[int] = None
    broker: Optional[str] = None             # alpaca | moomoo


@dataclass
class CommunicationMessage:
    """A message on the communication table (nervous system signal)."""
    id: int
    direction: str
    source: str
    target: Optional[str]
    msg_type: str
    identifier: Optional[str]
    payload: Optional[str]
    status: str
    created_at: str
    processed_at: Optional[str]
    processed_by: Optional[str]

    @classmethod
    def from_row(cls, row: dict) -> "CommunicationMessage":
        return cls(
            id=row["id"],
            direction=row["direction"],
            source=row["source"],
            target=row.get("target"),
            msg_type=row["msg_type"],
            identifier=row.get("identifier"),
            payload=row.get("payload"),
            status=row["status"],
            created_at=row["created_at"],
            processed_at=row.get("processed_at"),
            processed_by=row.get("processed_by"),
        )


@dataclass
class SignalMessage:
    """A signal on the signals table -- v8 architecture 3D signal bus."""
    id: int
    severity: str
    domain: str
    scope: str
    source: str
    content: str
    data: Optional[str]
    created_at: str
    expires_at: Optional[str]
    acknowledged_by: Optional[str]
    resolved: bool

    @classmethod
    def from_row(cls, row: dict) -> "SignalMessage":
        return cls(
            id=row["id"],
            severity=row["severity"],
            domain=row["domain"],
            scope=row["scope"],
            source=row["source"],
            content=row["content"],
            data=row.get("data"),
            created_at=row["created_at"],
            expires_at=row.get("expires_at"),
            acknowledged_by=row.get("acknowledged_by"),
            resolved=bool(row.get("resolved", 0)),
        )
