"""Parses standard syslog-format lines:
    '<Mon> <day> <HH:MM:SS> <host> <process>: <message>'
Best-effort: a line that doesn't match is skipped, not fatal — real syslog
streams routinely carry multi-line continuations and malformed entries.
"""

import re
from datetime import datetime

from core.detection.categories import infer_category_from_text
from core.detection.parsers.common import extract_ips, infer_severity_from_text
from data.models import Incident

_LINE_RE = re.compile(
    r"^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+(?P<process>[\w./-]+?):\s*(?P<message>.*)$"
)


def parse_syslog(text: str, *, year: int | None = None) -> list[Incident]:
    year = year or datetime.now().year
    incidents: list[Incident] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _LINE_RE.match(line)
        if not match:
            continue

        try:
            timestamp = datetime.strptime(
                f"{year} {match['month']} {match['day']} {match['time']}", "%Y %b %d %H:%M:%S"
            )
        except ValueError:
            continue

        message = match["message"]
        src_ip, dst_ip = extract_ips(message)
        incidents.append(
            Incident(
                id=None,
                scan_id=None,
                first_seen=timestamp,
                last_seen=timestamp,
                category=infer_category_from_text(message),
                severity=infer_severity_from_text(message),
                source=match["host"],
                src_ip=src_ip,
                dst_ip=dst_ip,
                description=message,
                raw=line,
            )
        )
    return incidents
