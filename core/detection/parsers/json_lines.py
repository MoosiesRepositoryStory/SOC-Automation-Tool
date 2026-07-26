"""Parses JSON incidents — either a JSON array of objects, or newline-
delimited JSON (one object per line). Recognized fields are optional and
defaulted; unrecognized fields are ignored (structured logs vary widely).
"""

import json

from core.detection.parsers.common import parse_severity, parse_timestamp
from data.models import Incident


def _object_to_incident(obj: dict) -> Incident:
    timestamp = parse_timestamp(obj.get("timestamp") or obj.get("time"))
    return Incident(
        id=None,
        scan_id=None,
        first_seen=timestamp,
        last_seen=timestamp,
        category=obj.get("category", "json"),
        severity=parse_severity(obj.get("severity") or obj.get("level")),
        source=obj.get("source") or obj.get("host", "unknown"),
        src_ip=obj.get("src_ip"),
        dst_ip=obj.get("dst_ip"),
        description=obj.get("message") or obj.get("description", ""),
        raw=json.dumps(obj),
    )


def parse_json(text: str) -> list[Incident]:
    text = text.strip()
    if not text:
        return []

    if text.startswith("["):
        objects = json.loads(text)
        return [_object_to_incident(obj) for obj in objects]

    incidents = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        incidents.append(_object_to_incident(obj))
    return incidents
