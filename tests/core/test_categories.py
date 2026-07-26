"""core/detection/categories.py — the inference logic half of the shared
taxonomy. IncidentCategory itself is tested implicitly through these
(it lives in data/models.py — see tests/data/ for the enum's own home)."""

from core.detection.categories import infer_category_from_text, parse_category
from data.models import IncidentCategory


def test_infer_category_matches_each_defined_keyword_group():
    cases = {
        "Failed password for root from 10.0.0.1": IncidentCategory.BRUTE_FORCE,
        "authentication failure for user admin": IncidentCategory.BRUTE_FORCE,
        "nmap scan detected from 10.0.0.5": IncidentCategory.PORT_SCAN,
        "port scan detected on 40 hosts": IncidentCategory.PORT_SCAN,
        "malware signature match: trojan.generic": IncidentCategory.MALWARE_EXECUTION,
        "ransomware behavior detected on host": IncidentCategory.MALWARE_EXECUTION,
        "SYN flood detected from 10.0.0.9": IncidentCategory.DENIAL_OF_SERVICE,
        "resource exhaustion on worker pool": IncidentCategory.DENIAL_OF_SERVICE,
        "unauthorized sudo attempt by user bob": IncidentCategory.PRIVILEGE_ESCALATION,
        "privilege escalation attempt blocked": IncidentCategory.PRIVILEGE_ESCALATION,
        "network reconnaissance detected from 10.0.0.2": IncidentCategory.DISCOVERY,
        "directory listing of /etc requested": IncidentCategory.DISCOVERY,
        "nightly backup completed successfully": IncidentCategory.UNCATEGORIZED,
        "disk usage at 80 percent": IncidentCategory.UNCATEGORIZED,
    }
    for message, expected in cases.items():
        assert infer_category_from_text(message) == expected, message


def test_infer_category_malware_keyword_wins_over_overlapping_generic_words():
    # "malware" and "failed" both appear — malware is checked first
    # (higher signal, less likely to be a false positive) and should win.
    result = infer_category_from_text("malware blocked after failed sandbox execution")
    assert result == IncidentCategory.MALWARE_EXECUTION


def test_parse_category_accepts_enum_value_string():
    assert parse_category("brute_force") == IncidentCategory.BRUTE_FORCE
    assert parse_category("port_scan") == IncidentCategory.PORT_SCAN


def test_parse_category_is_case_and_separator_insensitive():
    assert parse_category("Brute Force") == IncidentCategory.BRUTE_FORCE
    assert parse_category("BRUTE-FORCE") == IncidentCategory.BRUTE_FORCE
    assert parse_category("  brute_force  ") == IncidentCategory.BRUTE_FORCE


def test_parse_category_unrecognized_value_becomes_uncategorized_not_invented():
    assert parse_category("some_made_up_category") == IncidentCategory.UNCATEGORIZED


def test_parse_category_none_or_empty_becomes_uncategorized():
    assert parse_category(None) == IncidentCategory.UNCATEGORIZED
    assert parse_category("") == IncidentCategory.UNCATEGORIZED
