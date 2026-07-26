"""core/detection/parsers/ — no Qt involved, plain unit tests."""

from data.models import Severity
from core.detection.parsers import parse_csv, parse_json, parse_syslog

SYSLOG_SAMPLE = """Jul 26 10:15:32 web01 sshd: Failed password for root from 10.0.0.5
Jul 26 10:16:01 web01 kernel: critical hardware fault on disk sda
Jul 26 10:17:45 db02 cron: Notice: job completed successfully
not a valid syslog line at all
"""

JSON_ARRAY_SAMPLE = """[
    {"timestamp": "2026-07-26T11:00:00", "severity": "high", "source": "fw01", "src_ip": "10.0.0.9", "message": "port scan detected"},
    {"timestamp": "2026-07-26T11:05:00", "severity": "low", "message": "heartbeat ok"}
]"""

JSON_LINES_SAMPLE = (
    '{"timestamp": "2026-07-26T11:10:00", "severity": "critical", "source": "ids01", "message": "exploit attempt"}\n'
    '{"timestamp": "2026-07-26T11:11:00", "severity": "medium", "source": "ids01", "message": "suspicious dns query"}\n'
)

CSV_SAMPLE = (
    "timestamp,severity,source,src_ip,message\n"
    "2026-07-26 12:00:00,critical,edge01,192.168.1.5,malware signature match\n"
    "2026-07-26 12:01:00,medium,edge01,,unusual outbound volume\n"
)


def test_parse_syslog_skips_unmatched_lines_without_raising():
    incidents = parse_syslog(SYSLOG_SAMPLE, year=2026)
    assert len(incidents) == 3  # the 4th line is garbage and silently skipped


def test_parse_syslog_infers_severity_from_message_keywords():
    incidents = parse_syslog(SYSLOG_SAMPLE, year=2026)
    by_source = {inc.description: inc for inc in incidents}
    assert by_source["Failed password for root from 10.0.0.5"].severity == Severity.HIGH
    assert by_source["critical hardware fault on disk sda"].severity == Severity.CRITICAL
    assert by_source["Notice: job completed successfully"].severity == Severity.LOW


def test_parse_syslog_incidents_are_unpersisted():
    incidents = parse_syslog(SYSLOG_SAMPLE, year=2026)
    assert all(inc.id is None and inc.scan_id is None for inc in incidents)


def test_parse_json_handles_array_form():
    incidents = parse_json(JSON_ARRAY_SAMPLE)
    assert len(incidents) == 2
    assert incidents[0].source == "fw01"
    assert incidents[0].severity == Severity.HIGH
    assert incidents[0].src_ip == "10.0.0.9"
    assert incidents[1].source == "unknown"  # no source field -> default


def test_parse_json_handles_newline_delimited_form():
    incidents = parse_json(JSON_LINES_SAMPLE)
    assert len(incidents) == 2
    assert incidents[0].severity == Severity.CRITICAL
    assert incidents[1].severity == Severity.MEDIUM


def test_parse_csv_normalizes_rows():
    incidents = parse_csv(CSV_SAMPLE)
    assert len(incidents) == 2
    assert incidents[0].source == "edge01"
    assert incidents[0].severity == Severity.CRITICAL
    assert incidents[0].src_ip == "192.168.1.5"
    assert incidents[1].src_ip is None  # empty CSV field -> None, not ""


def test_parse_csv_empty_input_returns_empty_list():
    assert parse_csv("") == []


def test_parse_json_empty_input_returns_empty_list():
    assert parse_json("") == []
