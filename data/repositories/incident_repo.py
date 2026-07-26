"""Incident persistence: scans, incidents, and the append-only status
history. Zero Qt imports — see CLAUDE.md, Layering.

Status is never a mutable column — see docs/architecture.md §2. Every
status change is a new row in incident_status_history; "current status"
is always the latest row for that incident_id, derived on read.
"""

import sqlite3
from dataclasses import replace
from datetime import datetime

from data.models import Incident, IncidentRow, IncidentStatus, Scan, Severity


class IncidentRepository:
    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection

    # -- scans ------------------------------------------------------------

    def insert_scan(self, scan: Scan) -> Scan:
        cur = self._conn.execute(
            "INSERT INTO scans (started_at, source_path) VALUES (?, ?)",
            (scan.started_at.isoformat(), scan.source_path),
        )
        self._conn.commit()
        return replace(scan, id=cur.lastrowid)

    # -- incidents ----------------------------------------------------------

    def insert_incident(self, incident: Incident) -> Incident:
        cur = self._conn.execute(
            """
            INSERT INTO incidents
                (scan_id, first_seen, last_seen, category, severity,
                 source, src_ip, dst_ip, description, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident.scan_id,
                incident.first_seen.isoformat(),
                incident.last_seen.isoformat(),
                incident.category,
                incident.severity.value,
                incident.source,
                incident.src_ip,
                incident.dst_ip,
                incident.description,
                incident.raw,
            ),
        )
        self._conn.commit()
        persisted = replace(incident, id=cur.lastrowid)
        self.append_status(persisted.id, IncidentStatus.NEW, note="", changed_by="system")
        return persisted

    # -- status history (append-only) --------------------------------------

    def append_status(self, incident_id: int, status: IncidentStatus, note: str, changed_by: str) -> None:
        prev = self.current_status(incident_id)
        self._conn.execute(
            """
            INSERT INTO incident_status_history
                (incident_id, status, note, changed_at, changed_by, prev_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                status.value,
                note,
                datetime.now().isoformat(),
                changed_by,
                prev.value if prev else None,
            ),
        )
        self._conn.commit()

    def current_status(self, incident_id: int) -> IncidentStatus | None:
        row = self._conn.execute(
            """
            SELECT status FROM incident_status_history
            WHERE incident_id = ? ORDER BY id DESC LIMIT 1
            """,
            (incident_id,),
        ).fetchone()
        return IncidentStatus(row["status"]) if row else None

    def undo_last_status(self, incident_id: int) -> IncidentStatus | None:
        """Deletes the most recent history row, reverting to prev_status.
        Free, because status is append-only — see docs/architecture.md §2."""
        row = self._conn.execute(
            """
            SELECT id, prev_status FROM incident_status_history
            WHERE incident_id = ? ORDER BY id DESC LIMIT 1
            """,
            (incident_id,),
        ).fetchone()
        if row is None:
            return None
        self._conn.execute("DELETE FROM incident_status_history WHERE id = ?", (row["id"],))
        self._conn.commit()
        return IncidentStatus(row["prev_status"]) if row["prev_status"] else None

    # -- listing ------------------------------------------------------------

    def list_incident_rows(self) -> list[IncidentRow]:
        rows = self._conn.execute(
            """
            SELECT i.*,
                   (SELECT status FROM incident_status_history h
                     WHERE h.incident_id = i.id ORDER BY h.id DESC LIMIT 1) AS current_status,
                   (SELECT note FROM incident_status_history h
                     WHERE h.incident_id = i.id ORDER BY h.id DESC LIMIT 1) AS current_note
            FROM incidents i
            ORDER BY i.id
            """
        ).fetchall()

        result = []
        for row in rows:
            incident = Incident(
                id=row["id"],
                scan_id=row["scan_id"],
                first_seen=datetime.fromisoformat(row["first_seen"]),
                last_seen=datetime.fromisoformat(row["last_seen"]),
                category=row["category"],
                severity=Severity(row["severity"]),
                source=row["source"],
                src_ip=row["src_ip"],
                dst_ip=row["dst_ip"],
                description=row["description"],
                raw=row["raw"],
            )
            status = IncidentStatus(row["current_status"]) if row["current_status"] else IncidentStatus.NEW
            note = row["current_note"] or ""
            result.append(IncidentRow(incident=incident, status=status, note=note))
        return result
