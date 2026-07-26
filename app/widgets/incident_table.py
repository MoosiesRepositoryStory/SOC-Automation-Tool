"""Incident table: model + composable filter/search proxy + the page
widget wiring sorting, CSV export, context menus, fuzzy search, and
persisted column widths together.

Every text cell here supports selection/copy — QTableView gives this for
free via the standard item delegate, satisfying CLAUDE.md's copy-paste
sweep for this widget.
"""

import csv
import difflib
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from data.models import IncidentRow, IncidentStatus, Severity

# (key, header label, "explain this field" text for the header context menu)
COLUMNS: list[tuple[str, str, str]] = [
    ("id", "ID", "Internal database identifier. Not stable across a full DB rebuild."),
    ("first_seen", "First Seen", "Timestamp the underlying log event was first recorded."),
    ("category", "Category", "Detection category assigned by the parser that ingested this incident."),
    ("severity", "Severity", "Functional severity — critical/high/medium/low. Not brand-colored; see app/theme/tokens.py Severity."),
    ("source", "Source", "Host or system that generated the underlying log line."),
    ("src_ip", "Src IP", "Source IP extracted from the log line, if present."),
    ("dst_ip", "Dst IP", "Destination IP extracted from the log line, if present."),
    ("description", "Description", "The log message, or a normalized summary of it."),
    ("status", "Status", "Current triage status. Derived from the latest row in the append-only status history — never a mutable column, see docs/architecture.md §2."),
    ("note", "Note", "The analyst note attached to the most recent status change."),
]

_SEVERITY_RANK = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}


class IncidentTableModel(QAbstractTableModel):
    def __init__(self, rows: list[IncidentRow] | None = None, parent=None):
        super().__init__(parent)
        self._rows: list[IncidentRow] = rows or []

    def set_rows(self, rows: list[IncidentRow]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_at(self, source_row: int) -> IncidentRow:
        return self._rows[source_row]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section][1]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = COLUMNS[index.column()][0]

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return self._display_value(row, key)
        if role == Qt.ItemDataRole.UserRole:
            return self._sort_value(row, key)
        return None

    @staticmethod
    def _display_value(row: IncidentRow, key: str) -> str:
        incident = row.incident
        return {
            "id": str(incident.id),
            "first_seen": incident.first_seen.strftime("%Y-%m-%d %H:%M:%S"),
            "category": incident.category,
            "severity": incident.severity.value.capitalize(),
            "source": incident.source,
            "src_ip": incident.src_ip or "",
            "dst_ip": incident.dst_ip or "",
            "description": incident.description,
            "status": row.status.display_name,
            "note": row.note,
        }[key]

    def _sort_value(self, row: IncidentRow, key: str):
        if key == "first_seen":
            return row.incident.first_seen
        if key == "severity":
            return _SEVERITY_RANK[row.incident.severity]
        if key == "id":
            return row.incident.id or 0
        return self._display_value(row, key).lower()


class IncidentFilterProxyModel(QSortFilterProxyModel):
    """Per-column substring filters (AND-ed together) composed with a
    free-text search across all columns (AND-ed with the column filters).
    Qt's stock QSortFilterProxyModel only supports one column (or all-
    columns-OR'd) at a time — this subclass is what makes "full column
    filtering... composable with search" possible."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._column_filters: dict[int, str] = {}
        self._search_text: str = ""
        self.setSortRole(Qt.ItemDataRole.UserRole)

    def set_column_filter(self, column: int, text: str) -> None:
        text = text.strip()
        if text:
            self._column_filters[column] = text.lower()
        else:
            self._column_filters.pop(column, None)
        self.invalidate()

    def active_filter_columns(self) -> set[int]:
        return set(self._column_filters.keys())

    def set_search_text(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()

        for column, needle in self._column_filters.items():
            index = model.index(source_row, column, source_parent)
            value = str(model.data(index, Qt.ItemDataRole.DisplayRole) or "").lower()
            if needle not in value:
                return False

        if self._search_text:
            row_text = " ".join(
                str(model.data(model.index(source_row, col, source_parent), Qt.ItemDataRole.DisplayRole) or "")
                for col in range(model.columnCount())
            ).lower()
            if self._search_text not in row_text:
                return False

        return True


class IncidentTablePage(QWidget):
    _COLUMN_WIDTHS_TABLE_KEY = "incidents"

    def __init__(self, incident_repo, settings_service, parent: QWidget | None = None):
        super().__init__(parent)
        self._repo = incident_repo
        self._settings = settings_service

        self._model = IncidentTableModel()
        self._proxy = IncidentFilterProxyModel()
        self._proxy.setSourceModel(self._model)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search (Ctrl+F)…")
        self._search_box.textChanged.connect(self._on_search_text_changed)

        self._export_button = QPushButton("Export Filtered CSV…")
        self._export_button.clicked.connect(self._export_csv_dialog)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self._search_box, stretch=1)
        top_bar.addWidget(self._export_button)

        self._suggestion_label = QLabel()
        self._suggestion_label.setVisible(False)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)  # redundant with the explicit ID column

        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_row_context_menu)

        header = self._table.horizontalHeader()
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_context_menu)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.sectionResized.connect(self._on_section_resized)

        layout = QVBoxLayout(self)
        layout.addLayout(top_bar)
        layout.addWidget(self._suggestion_label)
        layout.addWidget(self._table)

        self._search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self._search_shortcut.activated.connect(self.focus_search)

        self._restore_column_widths()
        self.refresh()

    # -- data -------------------------------------------------------------

    def refresh(self) -> None:
        self._model.set_rows(self._repo.list_incident_rows())

    def table_view(self) -> QTableView:
        return self._table

    def proxy_model(self) -> IncidentFilterProxyModel:
        return self._proxy

    # -- search / fuzzy suggestions ----------------------------------------

    def focus_search(self) -> None:
        self._search_box.setFocus()

    def _on_search_text_changed(self, text: str) -> None:
        self._proxy.set_search_text(text)
        self._update_suggestion(text)

    def _update_suggestion(self, text: str) -> None:
        if not text.strip() or self._proxy.rowCount() > 0:
            self._suggestion_label.setVisible(False)
            return
        vocabulary = self._search_vocabulary()
        matches = difflib.get_close_matches(text.lower(), vocabulary, n=3, cutoff=0.6)
        if matches:
            self._suggestion_label.setText(f"No matches. Did you mean: {', '.join(matches)}?")
            self._suggestion_label.setVisible(True)
        else:
            self._suggestion_label.setText("No matches.")
            self._suggestion_label.setVisible(True)

    def _search_vocabulary(self) -> set[str]:
        vocabulary: set[str] = set()
        for row in range(self._model.rowCount()):
            for col in range(self._model.columnCount()):
                value = self._model.data(self._model.index(row, col), Qt.ItemDataRole.DisplayRole)
                if value:
                    text = str(value).lower()
                    vocabulary.add(text)
                    vocabulary.update(text.split())
        return vocabulary

    # -- column filters -----------------------------------------------------

    def set_column_filter(self, column: int, text: str) -> None:
        self._proxy.set_column_filter(column, text)

    def _prompt_column_filter(self, column: int, label: str) -> None:
        text, ok = QInputDialog.getText(self, f"Filter {label}", f"Show rows where {label} contains:")
        if ok:
            self.set_column_filter(column, text)

    # -- CSV export of the current filtered/sorted view ---------------------

    def export_filtered_csv(self, path: Path) -> None:
        headers = [label for _key, label, _explain in COLUMNS]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for proxy_row in range(self._proxy.rowCount()):
                values = [
                    self._proxy.data(self._proxy.index(proxy_row, col), Qt.ItemDataRole.DisplayRole) or ""
                    for col in range(self._proxy.columnCount())
                ]
                writer.writerow(values)

    def _export_csv_dialog(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self, "Export filtered incidents", "incidents.csv", "CSV files (*.csv)"
        )
        if path:
            self.export_filtered_csv(Path(path))

    # -- row context menu: status change ------------------------------------

    def apply_status_change(self, row: IncidentRow, status: IncidentStatus, note: str) -> None:
        self._repo.append_status(row.incident.id, status, note, changed_by="analyst")
        self.refresh()

    def build_row_context_menu(self, row: IncidentRow) -> QMenu:
        """Menu construction split from menu.exec() so tests (and the
        screenshot verification below) can build and show() a real menu
        without exec()'s blocking modal event loop, which never returns in
        an offscreen test with nothing to click."""
        menu = QMenu(self)
        for status in IncidentStatus:
            action = menu.addAction(f"Mark {status.display_name}")
            action.triggered.connect(lambda checked=False, s=status, r=row: self._change_status_via_dialog(r, s))
        return menu

    def _show_row_context_menu(self, pos) -> None:
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        source_index = self._proxy.mapToSource(index)
        row = self._model.row_at(source_index.row())
        menu = self.build_row_context_menu(row)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _change_status_via_dialog(self, row: IncidentRow, status: IncidentStatus) -> None:
        note, ok = QInputDialog.getMultiLineText(self, f"Mark {status.display_name}", "Note (optional):", "")
        if ok:
            self.apply_status_change(row, status, note)

    # -- header context menu: filter + explain field ------------------------

    def build_header_context_menu(self, logical_index: int) -> QMenu:
        """See build_row_context_menu's docstring — same split, same reason."""
        _key, label, explanation = COLUMNS[logical_index]

        menu = QMenu(self)
        filter_action = menu.addAction(f"Filter “{label}”…")
        filter_action.triggered.connect(lambda: self._prompt_column_filter(logical_index, label))

        if logical_index in self._proxy.active_filter_columns():
            clear_action = menu.addAction(f"Clear “{label}” filter")
            clear_action.triggered.connect(lambda: self.set_column_filter(logical_index, ""))

        menu.addSeparator()
        explain_action = menu.addAction(f"Explain “{label}”")
        explain_action.triggered.connect(lambda: QMessageBox.information(self, f"About: {label}", explanation))
        return menu

    def _show_header_context_menu(self, pos) -> None:
        logical_index = self._table.horizontalHeader().logicalIndexAt(pos)
        if logical_index < 0:
            return
        menu = self.build_header_context_menu(logical_index)
        menu.exec(self._table.horizontalHeader().mapToGlobal(pos))

    # -- persisted column widths --------------------------------------------

    def _restore_column_widths(self) -> None:
        widths = self._settings.column_widths(self._COLUMN_WIDTHS_TABLE_KEY)
        header = self._table.horizontalHeader()
        for col, width in widths.items():
            if 0 <= col < header.count():
                header.resizeSection(col, width)

    def _on_section_resized(self, *_args) -> None:
        header = self._table.horizontalHeader()
        widths = {i: header.sectionSize(i) for i in range(header.count())}
        self._settings.set_column_widths(self._COLUMN_WIDTHS_TABLE_KEY, widths)
