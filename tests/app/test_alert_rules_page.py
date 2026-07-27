"""app/widgets/alert_rules_page.py — Task 5d. Same offscreen pattern as
other widget tests. RuleEditorDialog is tested by constructing it and
driving its widgets directly, never calling .exec() — that blocks on user
interaction and would hang forever in an offscreen test with nothing to
click (same reasoning as incident_table.py's build_row_context_menu split).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.widgets.alert_rules_page import AlertRulesPage, ConditionRow, RuleEditorDialog
from data.db import connect
from data.models import AlertRule, Condition, ConditionField, ConditionOperator, IncidentCategory, Severity
from data.repositories.rule_repo import RuleRepository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT_DIR = PROJECT_ROOT / "docs" / "screenshots"


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def repo(tmp_path):
    conn = connect(tmp_path / "rules.db")
    return RuleRepository(conn)


# -- ConditionRow: value widget swaps by field type ---------------------------


def test_condition_row_uses_choice_combo_for_severity(qapp):
    row = ConditionRow()
    row._field_combo.setCurrentIndex(row._field_combo.findData(ConditionField.SEVERITY))
    assert row._value_stack.currentWidget() is row._value_choice_combo


def test_condition_row_uses_line_edit_for_source(qapp):
    row = ConditionRow()
    row._field_combo.setCurrentIndex(row._field_combo.findData(ConditionField.SOURCE))
    assert row._value_stack.currentWidget() is row._value_line_edit


def test_condition_row_round_trips_a_condition(qapp):
    original = Condition(ConditionField.CATEGORY, ConditionOperator.EQUALS, IncidentCategory.PORT_SCAN.value)
    row = ConditionRow(original)
    assert row.to_condition() == original


def test_condition_row_severity_choice_values_are_real_enum_values(qapp):
    row = ConditionRow()
    row._field_combo.setCurrentIndex(row._field_combo.findData(ConditionField.SEVERITY))
    choice_values = {row._value_choice_combo.itemData(i) for i in range(row._value_choice_combo.count())}
    assert choice_values == {s.value for s in Severity}


# -- RuleEditorDialog: driven directly, never .exec()'d -----------------------


def test_new_rule_dialog_starts_with_one_condition_row(qapp):
    dialog = RuleEditorDialog()
    assert len(dialog._condition_rows) == 1
    dialog.close()


def test_add_condition_button_adds_a_row(qapp):
    dialog = RuleEditorDialog()
    dialog._add_condition_row()
    assert len(dialog._condition_rows) == 2
    dialog.close()


def test_result_rule_reflects_entered_name_and_condition(qapp):
    dialog = RuleEditorDialog()
    dialog._name_edit.setText("My Rule")
    dialog._condition_rows[0]._value_line_edit.setText("ignored-if-choice")
    # default field is SEVERITY (first in enum) -> choice combo; pick HIGH
    row = dialog._condition_rows[0]
    row._value_choice_combo.setCurrentIndex(row._value_choice_combo.findData(Severity.HIGH.value))

    rule = dialog.result_rule()

    assert rule.name == "My Rule"
    assert rule.enabled is True
    assert rule.conditions == [Condition(ConditionField.SEVERITY, ConditionOperator.GTE, Severity.HIGH.value)]
    dialog.close()


def test_editing_existing_rule_prefills_dialog(qapp):
    existing = AlertRule(
        id=5,
        name="Existing",
        enabled=False,
        conditions=[Condition(ConditionField.SOURCE, ConditionOperator.CONTAINS, "web")],
    )
    dialog = RuleEditorDialog(rule=existing)

    assert dialog._name_edit.text() == "Existing"
    assert dialog._enabled_check.isChecked() is False
    assert dialog._condition_rows[0].to_condition() == existing.conditions[0]
    dialog.close()


def test_validation_error_without_name(qapp):
    dialog = RuleEditorDialog()
    dialog._condition_rows[0]._value_choice_combo.setCurrentIndex(0)  # give it a value
    assert dialog.validation_error() is not None
    dialog.close()


def test_validation_error_without_condition_value(qapp):
    dialog = RuleEditorDialog()
    dialog._name_edit.setText("Named but valueless")
    # default SEVERITY choice combo always has a selection, so switch to a
    # free-text field and leave it empty to hit the "no value" path
    row = dialog._condition_rows[0]
    row._field_combo.setCurrentIndex(row._field_combo.findData(ConditionField.SOURCE))
    row._value_line_edit.setText("")
    assert dialog.validation_error() is not None
    dialog.close()


def test_no_validation_error_with_name_and_value(qapp):
    dialog = RuleEditorDialog()
    dialog._name_edit.setText("Valid rule")
    dialog._condition_rows[0]._value_choice_combo.setCurrentIndex(0)
    assert dialog.validation_error() is None
    dialog.close()


# -- AlertRulesPage: list + context menu ---------------------------------------


def test_page_lists_inserted_rules(repo, qapp):
    repo.insert_rule(
        AlertRule(
            id=None,
            name="Rule One",
            enabled=True,
            conditions=[Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high")],
        )
    )
    page = AlertRulesPage(rule_repo=repo)
    assert page._table.rowCount() == 1
    assert page._table.item(0, 0).text() == "Rule One"
    assert page._table.item(0, 1).text() == "Yes"
    page.close()


def test_page_shows_match_count_column(repo, qapp):
    rule = repo.insert_rule(
        AlertRule(
            id=None,
            name="Rule",
            enabled=True,
            conditions=[Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high")],
        )
    )
    repo.record_match(rule.id, incident_id=1)
    repo.record_match(rule.id, incident_id=2)

    page = AlertRulesPage(rule_repo=repo)

    assert page._table.item(0, 3).text() == "2"
    page.close()


def test_context_menu_offers_toggle_edit_delete(repo, qapp):
    rule = repo.insert_rule(
        AlertRule(
            id=None,
            name="Rule",
            enabled=True,
            conditions=[Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high")],
        )
    )
    page = AlertRulesPage(rule_repo=repo)
    menu = page.build_context_menu(rule)
    labels = [action.text() for action in menu.actions()]
    assert "Disable" in labels  # enabled rule -> offers "Disable"
    assert any("Edit" in label for label in labels)
    assert "Delete" in labels
    page.close()


def test_toggle_enabled_updates_repo_and_refreshes(repo, qapp):
    rule = repo.insert_rule(
        AlertRule(
            id=None,
            name="Rule",
            enabled=True,
            conditions=[Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high")],
        )
    )
    page = AlertRulesPage(rule_repo=repo)
    page._toggle_enabled(rule)

    assert repo.get_rule(rule.id).enabled is False
    assert page._table.item(0, 1).text() == "No"
    page.close()


def test_delete_rule_removes_it_from_table(repo, qapp):
    rule = repo.insert_rule(
        AlertRule(
            id=None,
            name="Rule",
            enabled=True,
            conditions=[Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high")],
        )
    )
    page = AlertRulesPage(rule_repo=repo)
    page._delete_rule(rule.id)

    assert page._table.rowCount() == 0
    page.close()


# -- real screenshots -----------------------------------------------------------


def test_screenshot_rules_list_with_data(repo, qapp):
    repo.insert_rule(
        AlertRule(
            id=None,
            name="Critical brute force",
            enabled=True,
            conditions=[
                Condition(ConditionField.SEVERITY, ConditionOperator.GTE, "high"),
                Condition(ConditionField.CATEGORY, ConditionOperator.EQUALS, "brute_force"),
            ],
        )
    )
    r2 = repo.insert_rule(
        AlertRule(
            id=None,
            name="Web source scans",
            enabled=False,
            conditions=[Condition(ConditionField.SOURCE, ConditionOperator.CONTAINS, "web")],
        )
    )
    repo.record_match(r2.id, incident_id=1)

    page = AlertRulesPage(rule_repo=repo)
    page.resize(760, 320)
    page.show()
    qapp.processEvents()

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCREENSHOT_DIR / "alert_rules_list.png"
    assert page.grab().save(str(out_path))
    page.close()


def test_screenshot_rule_editor_dialog(qapp):
    dialog = RuleEditorDialog()
    dialog._name_edit.setText("Critical brute force from external IP")
    dialog._condition_rows[0]._value_choice_combo.setCurrentIndex(
        dialog._condition_rows[0]._value_choice_combo.findData(Severity.CRITICAL.value)
    )
    dialog._add_condition_row(Condition(ConditionField.CATEGORY, ConditionOperator.EQUALS, "brute_force"))
    dialog._add_condition_row(Condition(ConditionField.SRC_IP, ConditionOperator.CONTAINS, "203.0.113"))

    dialog.resize(520, 320)
    dialog.show()
    qapp.processEvents()

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCREENSHOT_DIR / "alert_rule_editor.png"
    assert dialog.grab().save(str(out_path))
    dialog.close()
