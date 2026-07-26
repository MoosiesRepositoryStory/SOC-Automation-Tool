"""Shared normalization helpers for the syslog/JSON/CSV parsers. Zero Qt
imports — see CLAUDE.md, Layering."""

import re
from datetime import datetime

from data.models import Severity

_IPV4 = r"(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)"
_SRC_IP_RE = re.compile(rf"\bfrom\s+({_IPV4})\b", re.IGNORECASE)
_DST_IP_RE = re.compile(rf"\bto\s+({_IPV4})\b", re.IGNORECASE)
_ANY_IP_RE = re.compile(rf"\b({_IPV4})\b")

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


def extract_ips(message: str) -> tuple[str | None, str | None]:
    """For free-text messages (syslog) with no dedicated src_ip/dst_ip
    field. Uses "from <ip>" / "to <ip>" as directional cues (matches the
    task's own example: "...from 203.0.113.9"). If neither cue is present
    but exactly one IPv4 address appears in the message, treats it as the
    source — the common case for auth/security log lines ("Failed
    password for root from 10.0.0.1") where a lone IP is the actor, not
    the target. Two or more un-cued IPs are left unassigned rather than
    guessed."""
    src_match = _SRC_IP_RE.search(message)
    dst_match = _DST_IP_RE.search(message)
    src_ip = src_match.group(1) if src_match else None
    dst_ip = dst_match.group(1) if dst_match else None

    if src_ip is None and dst_ip is None:
        all_ips = _ANY_IP_RE.findall(message)
        if len(all_ips) == 1:
            src_ip = all_ips[0]

    return src_ip, dst_ip


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
