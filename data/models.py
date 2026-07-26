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


class IncidentCategory(Enum):
    """Shared taxonomy — the single vocabulary every parser (core/detection/
    parsers/) and core/mitre.py's technique mapping key off of. Lives here,
    not in core/detection/categories.py, because Incident.category (below)
    needs the type and data/ must never import from core/ (CLAUDE.md,
    Layering) — core/detection/categories.py holds the *inference* logic
    and imports this enum from here, which is the allowed direction.

    Grounded in real ATT&CK tactic groupings, not arbitrary names — see
    core/mitre.py for exactly which verified technique IDs back each one.
    """

    BRUTE_FORCE = "brute_force"
    PORT_SCAN = "port_scan"
    MALWARE_EXECUTION = "malware_execution"
    DENIAL_OF_SERVICE = "dos"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DISCOVERY = "discovery"
    UNCATEGORIZED = "uncategorized"

    @property
    def display_name(self) -> str:
        return {
            IncidentCategory.BRUTE_FORCE: "Brute Force",
            IncidentCategory.PORT_SCAN: "Port Scan",
            IncidentCategory.MALWARE_EXECUTION: "Malware Execution",
            IncidentCategory.DENIAL_OF_SERVICE: "Denial of Service",
            IncidentCategory.PRIVILEGE_ESCALATION: "Privilege Escalation",
            IncidentCategory.DISCOVERY: "Discovery",
            IncidentCategory.UNCATEGORIZED: "Uncategorized",
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
    category: IncidentCategory
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
