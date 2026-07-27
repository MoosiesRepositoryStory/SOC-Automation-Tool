"""core/detection/alerting.py — pure logic, no Qt. Zero-match and
overlapping-rule cases get direct, explicit coverage per the task brief —
these are the two cases most likely to hide a real bug.
"""

from datetime import datetime

from core.detection.alerting import evaluate_rule, evaluate_rules
from data.models import (
    AlertRule,
    Condition,
    ConditionField,
    ConditionOperator,
    Incident,
    IncidentCategory,
    Severity,
)


def _incident(**overrides) -> Incident:
    defaults = dict(
        id=1,
        scan_id=1,
        first_seen=datetime(2026, 7, 26, 9, 0, 0),
        last_seen=datetime(2026, 7, 26, 9, 0, 0),
        category=IncidentCategory.BRUTE_FORCE,
        severity=Severity.HIGH,
        source="web01",
        src_ip="203.0.113.9",
        dst_ip=None,
        description="Failed password for root",
        raw="raw line",
    )
    defaults.update(overrides)
    return Incident(**defaults)


def _rule(*conditions: Condition, enabled: bool = True, name: str = "rule") -> AlertRule:
    return AlertRule(id=1, name=name, enabled=enabled, conditions=list(conditions))


# -- severity GTE/LTE ordering -----------------------------------------------


def test_severity_gte_matches_equal_and_more_severe():
    rule = _rule(Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high"))
    assert evaluate_rule(rule, _incident(severity=Severity.HIGH)) is True
    assert evaluate_rule(rule, _incident(severity=Severity.CRITICAL)) is True


def test_severity_gte_does_not_match_less_severe():
    rule = _rule(Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high"))
    assert evaluate_rule(rule, _incident(severity=Severity.MEDIUM)) is False
    assert evaluate_rule(rule, _incident(severity=Severity.LOW)) is False


def test_severity_lte_matches_equal_and_less_severe():
    rule = _rule(Condition(ConditionField.SEVERITY, ConditionOperator.LTE, "medium"))
    assert evaluate_rule(rule, _incident(severity=Severity.MEDIUM)) is True
    assert evaluate_rule(rule, _incident(severity=Severity.LOW)) is True
    assert evaluate_rule(rule, _incident(severity=Severity.HIGH)) is False


# -- category / string fields -------------------------------------------------


def test_category_equals():
    rule = _rule(Condition(ConditionField.CATEGORY, ConditionOperator.EQUALS, "brute_force"))
    assert evaluate_rule(rule, _incident(category=IncidentCategory.BRUTE_FORCE)) is True
    assert evaluate_rule(rule, _incident(category=IncidentCategory.PORT_SCAN)) is False


def test_source_contains_is_case_insensitive():
    rule = _rule(Condition(ConditionField.SOURCE, ConditionOperator.CONTAINS, "WEB"))
    assert evaluate_rule(rule, _incident(source="web01")) is True
    assert evaluate_rule(rule, _incident(source="db02")) is False


def test_string_field_none_value_treated_as_empty_not_error():
    rule = _rule(Condition(ConditionField.SRC_IP, ConditionOperator.EQUALS, "10.0.0.1"))
    # src_ip is None on this incident -- must not raise
    assert evaluate_rule(rule, _incident(src_ip=None)) is False


# -- AND-combination -----------------------------------------------------------


def test_and_combination_requires_every_condition():
    rule = _rule(
        Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high"),
        Condition(ConditionField.CATEGORY, ConditionOperator.EQUALS, "brute_force"),
    )
    # matches severity but not category
    assert evaluate_rule(rule, _incident(severity=Severity.CRITICAL, category=IncidentCategory.PORT_SCAN)) is False
    # matches both
    assert evaluate_rule(rule, _incident(severity=Severity.CRITICAL, category=IncidentCategory.BRUTE_FORCE)) is True


# -- zero-match case: explicitly required by the task brief -------------------


def test_rule_with_condition_that_matches_nothing_produces_no_match():
    rule = _rule(Condition(ConditionField.SOURCE, ConditionOperator.EQUALS, "nonexistent-host"))
    incident = _incident(source="web01")
    assert evaluate_rule(rule, incident) is False
    assert evaluate_rules([rule], incident) == []


def test_rule_with_zero_conditions_matches_nothing_not_everything():
    rule = _rule()  # no conditions at all
    assert evaluate_rule(rule, _incident()) is False


def test_disabled_rule_is_excluded_by_evaluate_rules_even_if_conditions_match():
    rule = _rule(Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "low"), enabled=False)
    incident = _incident(severity=Severity.CRITICAL)
    assert evaluate_rule(rule, incident) is True  # the rule's own logic matches...
    assert evaluate_rules([rule], incident) == []  # ...but evaluate_rules excludes disabled rules


# -- overlapping-rule case: explicitly required by the task brief -------------


def test_two_overlapping_rules_both_fire_independently():
    rule_a = _rule(Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high"), name="A")
    rule_b = _rule(Condition(ConditionField.CATEGORY, ConditionOperator.EQUALS, "brute_force"), name="B")
    incident = _incident(severity=Severity.HIGH, category=IncidentCategory.BRUTE_FORCE)

    matched = evaluate_rules([rule_a, rule_b], incident)

    assert len(matched) == 2
    assert {r.name for r in matched} == {"A", "B"}


def test_non_matching_rule_among_overlapping_set_is_excluded():
    rule_a = _rule(Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high"), name="A")
    rule_b = _rule(Condition(ConditionField.CATEGORY, ConditionOperator.EQUALS, "port_scan"), name="B")
    incident = _incident(severity=Severity.HIGH, category=IncidentCategory.BRUTE_FORCE)

    matched = evaluate_rules([rule_a, rule_b], incident)

    assert [r.name for r in matched] == ["A"]
