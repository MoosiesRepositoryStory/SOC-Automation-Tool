"""data/repositories/rule_repo.py — zero Qt, plain SQLite tests.

Extra scrutiny on record_match's idempotency: the UNIQUE(rule_id,
incident_id) constraint on alert_matches is what prevents a duplicate-
write when the same rule is evaluated against the same incident more than
once — checked directly here, not just trusted.
"""

import pytest

from data.db import connect
from data.models import AlertRule, Condition, ConditionField, ConditionOperator
from data.repositories.rule_repo import RuleRepository


@pytest.fixture
def repo(tmp_path):
    conn = connect(tmp_path / "rules.db")
    return RuleRepository(conn)


def _sample_rule(**overrides) -> AlertRule:
    defaults = dict(
        id=None,
        name="test rule",
        enabled=True,
        conditions=[Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high")],
    )
    defaults.update(overrides)
    return AlertRule(**defaults)


def test_insert_rule_assigns_id_and_round_trips_conditions(repo):
    rule = repo.insert_rule(_sample_rule())
    assert rule.id is not None

    fetched = repo.get_rule(rule.id)
    assert fetched == rule


def test_update_rule_persists_changes(repo):
    rule = repo.insert_rule(_sample_rule(name="original"))
    updated = repo.update_rule(
        AlertRule(id=rule.id, name="renamed", enabled=False, conditions=rule.conditions)
    )
    fetched = repo.get_rule(rule.id)
    assert fetched.name == "renamed"
    assert fetched.enabled is False


def test_set_enabled_toggles_without_touching_conditions(repo):
    rule = repo.insert_rule(_sample_rule())
    repo.set_enabled(rule.id, False)
    assert repo.get_rule(rule.id).enabled is False
    assert repo.get_rule(rule.id).conditions == rule.conditions


def test_list_enabled_rules_excludes_disabled(repo):
    enabled_rule = repo.insert_rule(_sample_rule(name="on"))
    disabled_rule = repo.insert_rule(_sample_rule(name="off", enabled=False))

    enabled = repo.list_enabled_rules()

    assert enabled_rule.id in [r.id for r in enabled]
    assert disabled_rule.id not in [r.id for r in enabled]


def test_delete_rule_also_removes_its_matches(repo):
    rule = repo.insert_rule(_sample_rule())
    repo.record_match(rule.id, incident_id=1)
    assert repo.match_count(rule.id) == 1

    repo.delete_rule(rule.id)

    assert repo.get_rule(rule.id) is None
    assert repo.match_count(rule.id) == 0


# -- match-history idempotency: explicitly required by the task brief --------


def test_record_match_is_new_the_first_time(repo):
    rule = repo.insert_rule(_sample_rule())
    assert repo.record_match(rule.id, incident_id=100) is True
    assert repo.has_matched(rule.id, incident_id=100) is True


def test_record_match_is_not_new_the_second_time_same_pair(repo):
    rule = repo.insert_rule(_sample_rule())
    repo.record_match(rule.id, incident_id=100)

    is_new_second_time = repo.record_match(rule.id, incident_id=100)

    assert is_new_second_time is False
    assert repo.match_count(rule.id) == 1  # not 2 -- no duplicate-write


def test_record_match_repeated_many_times_never_duplicates(repo):
    rule = repo.insert_rule(_sample_rule())
    for _ in range(5):
        repo.record_match(rule.id, incident_id=100)
    assert repo.match_count(rule.id) == 1


def test_different_incidents_are_independent_matches(repo):
    rule = repo.insert_rule(_sample_rule())
    repo.record_match(rule.id, incident_id=1)
    repo.record_match(rule.id, incident_id=2)
    assert repo.match_count(rule.id) == 2


def test_two_rules_matching_same_incident_both_recorded_independently(repo):
    """The overlapping-rule case at the persistence layer: two distinct
    (rule, incident) pairs are two distinct rows, not deduplicated against
    each other -- only a literal repeat of the SAME pair is suppressed."""
    rule_a = repo.insert_rule(_sample_rule(name="A"))
    rule_b = repo.insert_rule(_sample_rule(name="B"))

    assert repo.record_match(rule_a.id, incident_id=1) is True
    assert repo.record_match(rule_b.id, incident_id=1) is True

    assert repo.match_count() == 2
    assert repo.match_count(rule_a.id) == 1
    assert repo.match_count(rule_b.id) == 1
