"""core/pipeline.py — end-to-end: parse -> persist -> evaluate, through
ScanPipeline.run() exactly as the GUI would call it. Zero-match and
overlapping-rule cases repeated here at the full-pipeline level (not just
the unit level in tests/core/test_alerting.py), since wiring bugs live at
integration boundaries, not inside pure functions.
"""

import pytest

from core.pipeline import ScanPipeline
from data.db import connect
from data.models import AlertRule, Condition, ConditionField, ConditionOperator
from data.repositories.incident_repo import IncidentRepository
from data.repositories.rule_repo import RuleRepository

SYSLOG_LINE = "Jul 26 09:00:00 web01 sshd: Failed password for root from 203.0.113.9"


@pytest.fixture
def repos(tmp_path):
    conn = connect(tmp_path / "pipeline.db")
    return IncidentRepository(conn), RuleRepository(conn)


@pytest.fixture
def pipeline(repos):
    incident_repo, rule_repo = repos
    return ScanPipeline(incident_repo, rule_repo)


def test_run_parses_and_persists_incidents(pipeline):
    result = pipeline.run(SYSLOG_LINE, "syslog", "/var/log/auth.log")
    assert len(result.incidents) == 1
    assert result.incidents[0].id is not None
    assert result.incidents[0].source == "web01"


def test_run_rejects_unknown_source_format(pipeline):
    with pytest.raises(ValueError):
        pipeline.run(SYSLOG_LINE, "xml", "/var/log/auth.log")


# -- zero-match case, through the full pipeline -------------------------------


def test_rule_matching_nothing_produces_zero_matches(pipeline, repos):
    _incident_repo, rule_repo = repos
    zero_rule = rule_repo.insert_rule(
        AlertRule(
            id=None,
            name="never matches",
            enabled=True,
            conditions=[Condition(ConditionField.SOURCE, ConditionOperator.EQUALS, "nonexistent-host")],
        )
    )

    result = pipeline.run(SYSLOG_LINE, "syslog", "/var/log/auth.log")

    assert result.matches == []
    assert rule_repo.match_count(zero_rule.id) == 0


# -- overlapping-rule case, through the full pipeline -------------------------


def test_overlapping_rules_both_fire_through_full_pipeline(pipeline, repos):
    _incident_repo, rule_repo = repos
    rule_a = rule_repo.insert_rule(
        AlertRule(
            id=None,
            name="High+ severity",
            enabled=True,
            conditions=[Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high")],
        )
    )
    rule_b = rule_repo.insert_rule(
        AlertRule(
            id=None,
            name="Brute force",
            enabled=True,
            conditions=[Condition(ConditionField.CATEGORY, ConditionOperator.EQUALS, "brute_force")],
        )
    )

    result = pipeline.run(SYSLOG_LINE, "syslog", "/var/log/auth.log")

    assert len(result.matches) == 2
    matched_rule_ids = {m.rule.id for m in result.matches}
    assert matched_rule_ids == {rule_a.id, rule_b.id}
    # both matches point at the same incident, not two different ones
    assert len({m.incident.id for m in result.matches}) == 1

    assert rule_repo.match_count(rule_a.id) == 1
    assert rule_repo.match_count(rule_b.id) == 1
    assert rule_repo.match_count() == 2  # total, not deduplicated down to 1


def test_rerunning_pipeline_does_not_duplicate_matches_for_same_incident(pipeline, repos):
    """Not a realistic single-scan scenario (each run() call inserts new
    incidents), but directly exercises record_match's idempotency at the
    pipeline's own evaluation step, in case a future caller re-evaluates
    an existing incident set."""
    _incident_repo, rule_repo = repos
    rule = rule_repo.insert_rule(
        AlertRule(
            id=None,
            name="High+ severity",
            enabled=True,
            conditions=[Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high")],
        )
    )

    result = pipeline.run(SYSLOG_LINE, "syslog", "/var/log/auth.log")
    incident = result.incidents[0]
    assert rule_repo.match_count(rule.id) == 1

    # directly re-invoke the pipeline's evaluation step against the same
    # already-persisted incident
    rematches = pipeline._evaluate([incident])

    assert rematches == []  # already recorded -- not a new match
    assert rule_repo.match_count(rule.id) == 1  # still 1, not 2


def test_disabled_rule_does_not_fire(pipeline, repos):
    _incident_repo, rule_repo = repos
    rule = rule_repo.insert_rule(
        AlertRule(
            id=None,
            name="disabled",
            enabled=False,
            conditions=[Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "low")],
        )
    )

    result = pipeline.run(SYSLOG_LINE, "syslog", "/var/log/auth.log")

    assert result.matches == []
    assert rule_repo.match_count(rule.id) == 0
