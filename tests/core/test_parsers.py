"""core/detection/parsers/ — no Qt involved, plain unit tests."""

from core.detection.parsers import parse_csv, parse_json, parse_syslog
from core.detection.parsers.common import extract_ips
from data.models import IncidentCategory, Severity

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


# -- Task 5b: category inference + IP extraction, on realistic lines --------
# distinct from tests/core/test_categories.py (which tests the inference
# function directly) — these go through the full syslog line format,
# several lines beyond the one example in the task brief.

_REALISTIC_SYSLOG_LINES = {
    "Jul 26 09:00:00 web01 sshd: Failed password for root from 203.0.113.9": (
        IncidentCategory.BRUTE_FORCE,
        "203.0.113.9",
        None,
    ),
    "Jul 26 09:05:00 fw01 snort: nmap scan detected from 198.51.100.23": (
        IncidentCategory.PORT_SCAN,
        "198.51.100.23",
        None,
    ),
    "Jul 26 09:10:00 edge01 clamd: malware signature match: trojan.generic": (
        IncidentCategory.MALWARE_EXECUTION,
        None,
        None,
    ),
    "Jul 26 09:15:00 lb01 haproxy: SYN flood detected from 203.0.113.44": (
        IncidentCategory.DENIAL_OF_SERVICE,
        "203.0.113.44",
        None,
    ),
    "Jul 26 09:20:00 web01 sudo: unauthorized sudo attempt by user deploy": (
        IncidentCategory.PRIVILEGE_ESCALATION,
        None,
        None,
    ),
    "Jul 26 09:25:00 fw01 snort: connection to 10.0.0.50 blocked by policy": (
        IncidentCategory.UNCATEGORIZED,
        None,
        "10.0.0.50",
    ),
    "Jul 26 09:30:00 db02 cron: nightly backup completed successfully": (
        IncidentCategory.UNCATEGORIZED,
        None,
        None,
    ),
}


def test_parse_syslog_category_and_ip_on_realistic_lines():
    all_lines = "\n".join(_REALISTIC_SYSLOG_LINES.keys())
    incidents = parse_syslog(all_lines, year=2026)
    assert len(incidents) == len(_REALISTIC_SYSLOG_LINES)

    by_raw = {inc.raw: inc for inc in incidents}
    for line, (expected_category, expected_src, expected_dst) in _REALISTIC_SYSLOG_LINES.items():
        incident = by_raw[line]
        assert incident.category == expected_category, line
        assert incident.src_ip == expected_src, line
        assert incident.dst_ip == expected_dst, line


def test_extract_ips_from_cue_uses_from_and_to():
    assert extract_ips("Failed password for root from 203.0.113.9") == ("203.0.113.9", None)
    assert extract_ips("connection to 10.0.0.50 blocked by policy") == (None, "10.0.0.50")


def test_extract_ips_single_uncued_ip_assumed_source():
    assert extract_ips("suspicious activity involving 10.0.0.7") == ("10.0.0.7", None)


def test_extract_ips_two_uncued_ips_left_unassigned():
    # No "from"/"to" cue and more than one IP present — ambiguous which is
    # which, so neither is guessed.
    assert extract_ips("traffic between 10.0.0.1 and 10.0.0.2 anomalous") == (None, None)


def test_extract_ips_no_ip_present():
    assert extract_ips("nightly backup completed successfully") == (None, None)


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
