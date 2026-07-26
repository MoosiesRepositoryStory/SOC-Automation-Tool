"""Shared normalization helpers for the syslog/JSON/CSV parsers. Zero Qt
imports — see CLAUDE.md, Layering."""

from datetime import datetime

from data.models import Severity

_SEVERITY_ALIASES = {
    "critical": Severity.CRITICAL,
    "crit": Severity.CRITICAL,
    "emerg": Severity.CRITICAL,
    "alert": Severity.CRITICAL,
    "panic": Severity.CRITICAL,
    "high": Severity.HIGH,
    "error": Severity.HIGH,
    "err": Severity.HIGH,
    "fail": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "warn": Severity.MEDIUM,
    "warning": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.LOW,
    "notice": Severity.LOW,
    "debug": Severity.LOW,
}


def parse_severity(value: str | None) -> Severity:
    """Exact-match lookup — for structured fields (JSON/CSV 'severity' or
    'level' columns) where the value IS the severity keyword."""
    if value is None:
        return Severity.LOW
    return _SEVERITY_ALIASES.get(str(value).strip().lower(), Severity.LOW)


def infer_severity_from_text(message: str) -> Severity:
    """Substring keyword search — for free-text log messages (syslog) with
    no dedicated severity field. First keyword match wins, checked in
    severity order so 'critical failure' resolves to CRITICAL, not HIGH."""
    lowered = message.lower()
    for severity in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW):
        keywords = [kw for kw, sev in _SEVERITY_ALIASES.items() if sev == severity]
        if any(kw in lowered for kw in keywords):
            return severity
    return Severity.LOW


def parse_timestamp(value) -> datetime:
    if value is None:
        return datetime.now()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    text = str(value)[:19]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.now()
