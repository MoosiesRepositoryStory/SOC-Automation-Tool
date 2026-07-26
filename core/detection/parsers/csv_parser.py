"""Parses CSV incidents. Expects a header row; recognized column names
are case-insensitive and optional — anything missing is defaulted."""

import csv
import io

from core.detection.categories import parse_category
from core.detection.parsers.common import parse_severity, parse_timestamp
from data.models import Incident


def parse_csv(text: str) -> list[Incident]:
    reader = csv.DictReader(io.StringIO(text))
    incidents = []

    for row in reader:
        normalized = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        timestamp = parse_timestamp(normalized.get("timestamp") or normalized.get("time"))
        incidents.append(
            Incident(
                id=None,
                scan_id=None,
                first_seen=timestamp,
                last_seen=timestamp,
                category=parse_category(normalized.get("category")),
                severity=parse_severity(normalized.get("severity") or normalized.get("level")),
                source=normalized.get("source") or normalized.get("host") or "unknown",
                src_ip=normalized.get("src_ip") or None,
                dst_ip=normalized.get("dst_ip") or None,
                description=normalized.get("message") or normalized.get("description") or "",
                raw=",".join(row.values()),
            )
        )
    return incidents
