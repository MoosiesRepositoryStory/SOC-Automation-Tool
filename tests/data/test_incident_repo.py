"""data/repositories/incident_repo.py — zero Qt, plain SQLite tests.

Extra scrutiny on the append-only status history: this is the design
decision docs/architecture.md flags as the one that matters most (false-
positive-rate-over-time is impossible from a mutable column), so it's
tested directly here, not just trusted.
"""

from datetime import datetime

import pytest

from data.db import connect
from data.models import Incident, IncidentCategory, IncidentStatus, Scan, Severity
from data.repositories.incident_repo import IncidentRepository


@pytest.fixture
def repo(tmp_path):
    conn = connect(tmp_path / "test.db")
    return IncidentRepository(conn)


def _sample_incident(**overrides) -> Incident:
    defaults = dict(
        id=None,
        scan_id=None,
        first_seen=datetime(2026, 7, 26, 12, 0, 0),
        last_seen=datetime(2026, 7, 26, 12, 0, 0),
        category=IncidentCategory.BRUTE_FORCE,
        severity=Severity.HIGH,
        source="host01",
        src_ip="10.0.0.1",
        dst_ip=None,
        description="test incident",
        raw="raw log line",
    )
    defaults.update(overrides)
    return Incident(**defaults)


def test_insert_incident_assigns_id_and_defaults_to_new_status(repo):
    incident = repo.insert_incident(_sample_incident())
    assert incident.id is not None
    assert repo.current_status(incident.id) == IncidentStatus.NEW


def test_status_history_is_append_only_not_overwritten(repo):
    """The core guarantee: marking an incident Investigating then Resolved
    must leave BOTH transitions in incident_status_history, not just the
    latest value. This is what makes false-positive-rate-over-time
    possible at all."""
    incident = repo.insert_incident(_sample_incident())

    repo.append_status(incident.id, IncidentStatus.INVESTIGATING, "looking into it", "analyst1")
    repo.append_status(incident.id, IncidentStatus.RESOLVED, "confirmed benign", "analyst1")

    history_count = repo._conn.execute(
        "SELECT COUNT(*) FROM incident_status_history WHERE incident_id = ?", (incident.id,)
    ).fetchone()[0]
    # NEW (on insert) + INVESTIGATING + RESOLVED = 3 rows, not 1
    assert history_count == 3
    assert repo.current_status(incident.id) == IncidentStatus.RESOLVED


def test_append_status_records_prev_status_for_free_undo(repo):
    incident = repo.insert_incident(_sample_incident())
    repo.append_status(incident.id, IncidentStatus.INVESTIGATING, "", "analyst1")

    reverted = repo.undo_last_status(incident.id)

    assert reverted == IncidentStatus.NEW
    assert repo.current_status(incident.id) == IncidentStatus.NEW


def test_list_incident_rows_reflects_latest_status_and_note(repo):
    incident = repo.insert_incident(_sample_incident(description="alpha"))
    repo.append_status(incident.id, IncidentStatus.FALSE_POSITIVE, "confirmed noise", "analyst2")

    rows = repo.list_incident_rows()
    assert len(rows) == 1
    assert rows[0].status == IncidentStatus.FALSE_POSITIVE
    assert rows[0].note == "confirmed noise"
    assert rows[0].incident.description == "alpha"


def test_insert_scan_links_to_incidents(repo):
    scan = repo.insert_scan(Scan(id=None, started_at=datetime(2026, 7, 26, 9, 0, 0), source_path="/var/log/sample.log"))
    incident = repo.insert_incident(_sample_incident(scan_id=scan.id))

    rows = repo.list_incident_rows()
    assert rows[0].incident.scan_id == scan.id
