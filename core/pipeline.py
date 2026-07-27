"""Scan pipeline: parse -> persist -> evaluate alert rules. Zero Qt
imports (CLAUDE.md, Layering) — the GUI calls ScanPipeline.run(), never
reimplements this inline (docs/architecture.md §1).

Didn't exist before Task 5d; architecture.md already named it
(`core/pipeline.py: ScanPipeline.run() -> ScanResult`) as part of Task 1's
decided module boundaries, so this fills in already-decided structure
rather than inventing new scope. The Qt signal that surfaces matches to
the UI lives in app/alert_service.py, not here.
"""

from dataclasses import dataclass, replace
from datetime import datetime

from core.detection.alerting import evaluate_rules
from core.detection.parsers import parse_csv, parse_json, parse_syslog
from data.models import AlertRule, Incident, Scan
from data.repositories.incident_repo import IncidentRepository
from data.repositories.rule_repo import RuleRepository

_PARSERS = {
    "syslog": parse_syslog,
    "json": parse_json,
    "csv": parse_csv,
}


@dataclass(frozen=True)
class RuleMatch:
    rule: AlertRule
    incident: Incident


@dataclass(frozen=True)
class ScanResult:
    scan: Scan
    incidents: list[Incident]
    matches: list[RuleMatch]


class ScanPipeline:
    def __init__(self, incident_repo: IncidentRepository, rule_repo: RuleRepository):
        self._incidents = incident_repo
        self._rules = rule_repo

    def run(self, text: str, source_format: str, source_path: str) -> ScanResult:
        if source_format not in _PARSERS:
            raise ValueError(f"unknown source_format {source_format!r}, expected one of {list(_PARSERS)}")

        parsed = _PARSERS[source_format](text)
        scan = self._incidents.insert_scan(
            Scan(id=None, started_at=datetime.now(), source_path=source_path)
        )

        persisted = [
            self._incidents.insert_incident(replace(incident, scan_id=scan.id)) for incident in parsed
        ]

        matches = self._evaluate(persisted)
        return ScanResult(scan=scan, incidents=persisted, matches=matches)

    def _evaluate(self, incidents: list[Incident]) -> list[RuleMatch]:
        """Runs every enabled rule against every new incident. record_match
        is the idempotency boundary (UNIQUE(rule_id, incident_id) in
        data/db.py) -- two rules matching the same incident both produce a
        RuleMatch, since each is a genuinely distinct (rule, incident)
        pair; only a literal re-run of the same pair is suppressed."""
        enabled_rules = self._rules.list_enabled_rules()
        matches: list[RuleMatch] = []
        for incident in incidents:
            for rule in evaluate_rules(enabled_rules, incident):
                is_new = self._rules.record_match(rule.id, incident.id)
                if is_new:
                    matches.append(RuleMatch(rule=rule, incident=incident))
        return matches
