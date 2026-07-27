"""Alert rule evaluation — pure logic, zero Qt imports (CLAUDE.md,
Layering). AlertRule/Condition dataclasses live in data/models.py, same
split as core/detection/categories.py for IncidentCategory: the data
shape lives in data/, the logic that interprets it lives here.
"""

from data.models import (
    AlertRule,
    Condition,
    ConditionField,
    ConditionOperator,
    Incident,
    Severity,
)

# Lower rank = more severe. Used for GTE/LTE ("at least/most as severe as").
_SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


def _field_value(incident: Incident, field: ConditionField):
    return {
        ConditionField.SEVERITY: incident.severity,
        ConditionField.CATEGORY: incident.category,
        ConditionField.SOURCE: incident.source,
        ConditionField.SRC_IP: incident.src_ip,
        ConditionField.DST_IP: incident.dst_ip,
        ConditionField.DESCRIPTION: incident.description,
    }[field]


def _evaluate_severity(condition: Condition, actual: Severity) -> bool:
    try:
        expected = Severity(condition.value)
    except ValueError:
        return False

    actual_rank = _SEVERITY_RANK[actual]
    expected_rank = _SEVERITY_RANK[expected]

    if condition.operator == ConditionOperator.GTE:
        return actual_rank <= expected_rank
    if condition.operator == ConditionOperator.LTE:
        return actual_rank >= expected_rank
    if condition.operator == ConditionOperator.EQUALS:
        return actual == expected
    if condition.operator == ConditionOperator.NOT_EQUALS:
        return actual != expected
    return False


def _evaluate_string(condition: Condition, actual: str | None) -> bool:
    actual = actual or ""
    if condition.operator == ConditionOperator.EQUALS:
        return actual == condition.value
    if condition.operator == ConditionOperator.NOT_EQUALS:
        return actual != condition.value
    if condition.operator == ConditionOperator.CONTAINS:
        return condition.value.lower() in actual.lower()
    return False


def _evaluate_condition(condition: Condition, incident: Incident) -> bool:
    actual = _field_value(incident, condition.field)

    if condition.field == ConditionField.SEVERITY:
        return _evaluate_severity(condition, actual)

    if condition.field == ConditionField.CATEGORY:
        if condition.operator == ConditionOperator.EQUALS:
            return actual is not None and actual.value == condition.value
        if condition.operator == ConditionOperator.NOT_EQUALS:
            return actual is None or actual.value != condition.value
        return False

    return _evaluate_string(condition, actual)


def evaluate_rule(rule: AlertRule, incident: Incident) -> bool:
    """AND-combined — every condition must match. A rule with zero
    conditions matches nothing (see AlertRule's docstring in
    data/models.py) rather than everything."""
    if not rule.conditions:
        return False
    return all(_evaluate_condition(condition, incident) for condition in rule.conditions)


def evaluate_rules(rules: list[AlertRule], incident: Incident) -> list[AlertRule]:
    """Every enabled rule is evaluated independently against the same
    incident. Two rules matching the same incident both appear in the
    result — one match never suppresses another."""
    return [rule for rule in rules if rule.enabled and evaluate_rule(rule, incident)]
