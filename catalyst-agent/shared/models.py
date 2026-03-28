"""
Name of Application: Catalyst Trading System
Name of file: models.py
Version: 1.0.0
Last Updated: 2026-03-03
Purpose: Shared enums and dataclasses for agent body components

REVISION HISTORY:
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


class Component(str, Enum):
    """Brain components that communicate via the nervous system."""
    PFC = "pfc"
    OCCIPITAL = "occipital"
    CEREBELLUM = "cerebellum"
    HIPPOCAMPUS = "hippocampus"
    BROADCAST = "broadcast"


class MessageType(str, Enum):
    """Types of messages on the communication table."""
    TASK = "task"
    RESULT = "result"
    SIGNAL = "signal"
    STATUS = "status"
    ESCALATION = "escalation"


class Direction(str, Enum):
    """Signal direction on the nervous system."""
    DESCENDING = "descending"  # PFC to components (task/intent)
    ASCENDING = "ascending"    # Components to PFC (result/perception)


class PFCMode(str, Enum):
    """PFC operating modes — what the whole body is configured for."""
    SLEEPING = "sleeping"
    WAKING = "waking"
    LEARNING = "learning"
    EXECUTING = "executing"
    PONDERING = "pondering"
    RELAXING = "relaxing"
    EMERGENCY = "emergency"


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
