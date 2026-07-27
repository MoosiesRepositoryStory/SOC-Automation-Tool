"""Alert rules UI: list existing rules, create/edit/enable/disable/delete.
See core/detection/alerting.py for how the conditions built here actually
get evaluated, and data/models.py's AlertRule docstring for why an empty
condition list is refused rather than silently matching everything.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data.models import AlertRule, Condition, ConditionField, ConditionOperator, IncidentCategory, Severity

_FIELD_LABELS = {
    ConditionField.SEVERITY: "Severity",
    ConditionField.CATEGORY: "Category",
    ConditionField.SOURCE: "Source",
    ConditionField.SRC_IP: "Src IP",
    ConditionField.DST_IP: "Dst IP",
    ConditionField.DESCRIPTION: "Description",
}

_OPERATOR_LABELS = {
    ConditionOperator.EQUALS: "is",
    ConditionOperator.NOT_EQUALS: "is not",
    ConditionOperator.GTE: "is at least",
    ConditionOperator.LTE: "is at most",
    ConditionOperator.CONTAINS: "contains",
}

_OPERATORS_FOR_FIELD = {
    ConditionField.SEVERITY: [
        ConditionOperator.GTE,
        ConditionOperator.LTE,
        ConditionOperator.EQUALS,
        ConditionOperator.NOT_EQUALS,
    ],
    ConditionField.CATEGORY: [ConditionOperator.EQUALS, ConditionOperator.NOT_EQUALS],
    ConditionField.SOURCE: [ConditionOperator.EQUALS, ConditionOperator.NOT_EQUALS, ConditionOperator.CONTAINS],
    ConditionField.SRC_IP: [ConditionOperator.EQUALS, ConditionOperator.NOT_EQUALS, ConditionOperator.CONTAINS],
    ConditionField.DST_IP: [ConditionOperator.EQUALS, ConditionOperator.NOT_EQUALS, ConditionOperator.CONTAINS],
    ConditionField.DESCRIPTION: [ConditionOperator.CONTAINS],
}

_CHOICE_FIELDS = {
    ConditionField.SEVERITY: [(s.value.capitalize(), s.value) for s in Severity],
    ConditionField.CATEGORY: [(c.display_name, c.value) for c in IncidentCategory],
}


class ConditionRow(QWidget):
    """One AND-term: field + operator + value. The value widget swaps
    between a QComboBox (severity/category — fixed, valid choices only,
    so a rule can't silently zero-match from a typo) and a QLineEdit
    (source/IP/description — free text)."""

    def __init__(self, condition: Condition | None = None, parent: QWidget | None = None):
        super().__init__(parent)

        self._field_combo = QComboBox()
        for field in ConditionField:
            self._field_combo.addItem(_FIELD_LABELS[field], field)
        self._field_combo.currentIndexChanged.connect(self._on_field_changed)

        self._operator_combo = QComboBox()

        self._value_line_edit = QLineEdit()
        self._value_choice_combo = QComboBox()
        self._value_stack = QStackedWidget()
        self._value_stack.addWidget(self._value_line_edit)
        self._value_stack.addWidget(self._value_choice_combo)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._field_combo)
        layout.addWidget(self._operator_combo)
        layout.addWidget(self._value_stack, stretch=1)

        self._on_field_changed(0)
        if condition is not None:
            self._set_condition(condition)

    def _on_field_changed(self, _index: int) -> None:
        field = self._field_combo.currentData()

        self._operator_combo.clear()
        for op in _OPERATORS_FOR_FIELD[field]:
            self._operator_combo.addItem(_OPERATOR_LABELS[op], op)

        if field in _CHOICE_FIELDS:
            self._value_choice_combo.clear()
            for label, value in _CHOICE_FIELDS[field]:
                self._value_choice_combo.addItem(label, value)
            self._value_stack.setCurrentWidget(self._value_choice_combo)
        else:
            self._value_stack.setCurrentWidget(self._value_line_edit)

    def _set_condition(self, condition: Condition) -> None:
        self._field_combo.setCurrentIndex(self._field_combo.findData(condition.field))
        self._on_field_changed(self._field_combo.currentIndex())  # ensure operator/value populated for this field
        self._operator_combo.setCurrentIndex(self._operator_combo.findData(condition.operator))
        if self._value_stack.currentWidget() is self._value_choice_combo:
            self._value_choice_combo.setCurrentIndex(self._value_choice_combo.findData(condition.value))
        else:
            self._value_line_edit.setText(condition.value)

    def to_condition(self) -> Condition:
        field = self._field_combo.currentData()
        operator = self._operator_combo.currentData()
        if self._value_stack.currentWidget() is self._value_choice_combo:
            value = self._value_choice_combo.currentData()
        else:
            value = self._value_line_edit.text().strip()
        return Condition(field=field, operator=operator, value=value)


class RuleEditorDialog(QDialog):
    def __init__(self, rule: AlertRule | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Alert Rule" if rule else "New Alert Rule")
        self.setMinimumWidth(480)

        self._rule_id = rule.id if rule else None
        self._condition_rows: list[ConditionRow] = []

        self._name_edit = QLineEdit(rule.name if rule else "")
        self._name_edit.setPlaceholderText("Rule name")

        self._enabled_check = QCheckBox("Enabled")
        self._enabled_check.setChecked(rule.enabled if rule else True)

        self._conditions_layout = QVBoxLayout()
        if rule and rule.conditions:
            for condition in rule.conditions:
                self._add_condition_row(condition)
        else:
            self._add_condition_row()

        add_condition_button = QPushButton("+ Add Condition")
        add_condition_button.clicked.connect(lambda: self._add_condition_row())

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Name:"))
        layout.addWidget(self._name_edit)
        layout.addWidget(self._enabled_check)
        layout.addWidget(QLabel("Conditions (all must match):"))
        layout.addLayout(self._conditions_layout)
        layout.addWidget(add_condition_button)
        layout.addWidget(self._buttons)

    def _add_condition_row(self, condition: Condition | None = None) -> None:
        row = ConditionRow(condition)
        self._condition_rows.append(row)
        self._conditions_layout.addWidget(row)

    def validation_error(self) -> str | None:
        """Pure validation, no dialog -- split out so it's testable without
        triggering QMessageBox.warning()'s own blocking exec() loop (same
        reasoning as build_row_context_menu elsewhere: a modal call with
        nothing to click hangs forever in an offscreen test)."""
        if not self._name_edit.text().strip():
            return "Give this rule a name before saving."
        if not any(row.to_condition().value for row in self._condition_rows):
            return (
                "A rule needs at least one condition with a value — an empty rule "
                "would match nothing (see data/models.py's AlertRule docstring)."
            )
        return None

    def _on_accept(self) -> None:
        error = self.validation_error()
        if error is not None:
            QMessageBox.warning(self, "Can't save this rule", error)
            return
        self.accept()

    def result_rule(self) -> AlertRule:
        conditions = [row.to_condition() for row in self._condition_rows if row.to_condition().value]
        return AlertRule(
            id=self._rule_id,
            name=self._name_edit.text().strip(),
            enabled=self._enabled_check.isChecked(),
            conditions=conditions,
        )


class AlertRulesPage(QWidget):
    _COLUMNS = ("Name", "Enabled", "Conditions", "Matches")

    def __init__(self, rule_repo, parent: QWidget | None = None):
        super().__init__(parent)
        self._repo = rule_repo

        self._new_button = QPushButton("New Rule…")
        self._new_button.clicked.connect(self._on_new_rule)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self._new_button)
        top_bar.addStretch(1)

        self._table = QTableWidget(0, len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(list(self._COLUMNS))
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.doubleClicked.connect(lambda index: self._edit_rule(index.row()))

        layout = QVBoxLayout(self)
        layout.addLayout(top_bar)
        layout.addWidget(self._table)

        self.refresh()

    def refresh(self) -> None:
        rules = self._repo.list_rules()
        self._table.setRowCount(len(rules))
        for row_index, rule in enumerate(rules):
            name_item = QTableWidgetItem(rule.name)
            name_item.setData(Qt.ItemDataRole.UserRole, rule.id)
            self._table.setItem(row_index, 0, name_item)
            self._table.setItem(row_index, 1, QTableWidgetItem("Yes" if rule.enabled else "No"))
            self._table.setItem(row_index, 2, QTableWidgetItem(self._summarize(rule)))
            self._table.setItem(row_index, 3, QTableWidgetItem(str(self._repo.match_count(rule.id))))

    @staticmethod
    def _summarize(rule: AlertRule) -> str:
        parts = [
            f"{_FIELD_LABELS[c.field]} {_OPERATOR_LABELS[c.operator]} {c.value}" for c in rule.conditions
        ]
        return " AND ".join(parts) if parts else "(no conditions — matches nothing)"

    def _rule_id_at_row(self, row: int) -> int:
        return self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _rule_at_row(self, row: int) -> AlertRule:
        return self._repo.get_rule(self._rule_id_at_row(row))

    def _on_new_rule(self) -> None:
        dialog = RuleEditorDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._repo.insert_rule(dialog.result_rule())
            self.refresh()

    def _edit_rule(self, row: int) -> None:
        rule = self._rule_at_row(row)
        dialog = RuleEditorDialog(rule=rule, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._repo.update_rule(dialog.result_rule())
            self.refresh()

    def build_context_menu(self, rule: AlertRule) -> QMenu:
        """Split from menu.exec() for the same reason as
        incident_table.py's build_row_context_menu — testable/screenshot-
        able via .show() without exec()'s blocking modal loop."""
        menu = QMenu(self)
        toggle_action = menu.addAction("Disable" if rule.enabled else "Enable")
        toggle_action.triggered.connect(lambda: self._toggle_enabled(rule))
        edit_action = menu.addAction("Edit…")
        edit_action.triggered.connect(lambda: self._edit_rule_by_id(rule.id))
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self._delete_rule(rule.id))
        return menu

    def _edit_rule_by_id(self, rule_id: int) -> None:
        for row in range(self._table.rowCount()):
            if self._rule_id_at_row(row) == rule_id:
                self._edit_rule(row)
                return

    def _show_context_menu(self, pos) -> None:
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        rule = self._rule_at_row(index.row())
        menu = self.build_context_menu(rule)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _toggle_enabled(self, rule: AlertRule) -> None:
        self._repo.set_enabled(rule.id, not rule.enabled)
        self.refresh()

    def _delete_rule(self, rule_id: int) -> None:
        self._repo.delete_rule(rule_id)
        self.refresh()
