"""Domain dataclasses crossing the app/core/data boundary. Zero Qt imports
— see CLAUDE.md, Layering.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(Enum):
    NEW = "new"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"

    @property
    def display_name(self) -> str:
        return {
            IncidentStatus.NEW: "New",
            IncidentStatus.INVESTIGATING: "Investigating",
            IncidentStatus.RESOLVED: "Resolved",
            IncidentStatus.FALSE_POSITIVE: "False Positive",
        }[self]


@dataclass(frozen=True)
class Scan:
    id: int | None
    started_at: datetime
    source_path: str


@dataclass(frozen=True)
class Incident:
    """id/scan_id are None until IncidentRepository.insert_incident persists
    it — parsers in core/detection/parsers/ produce these unpersisted."""

    id: int | None
    scan_id: int | None
    first_seen: datetime
    last_seen: datetime
    category: str
    severity: Severity
    source: str
    src_ip: str | None
    dst_ip: str | None
    description: str
    raw: str


@dataclass(frozen=True)
class IncidentStatusEntry:
    id: int | None
    incident_id: int
    status: IncidentStatus
    note: str
    changed_at: datetime
    changed_by: str
    prev_status: IncidentStatus | None


@dataclass(frozen=True)
class IncidentRow:
    """Incident + its current status + latest note — what the table
    displays. Always derived from the append-only history, never itself
    persisted (see docs/architecture.md §2: status is never a mutable
    column)."""

    incident: Incident
    status: IncidentStatus
    note: str
