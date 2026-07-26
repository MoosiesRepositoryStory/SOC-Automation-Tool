"""Task 5a — incident table: column filtering + search composability,
sorting, CSV export of the filtered/sorted view, context menus, fuzzy
search, and persisted column widths.

Same headless pattern as tests/theme/test_contrast.py and
tests/nav/test_nav_position.py: QT_QPA_PLATFORM=offscreen. Real screenshots
saved to docs/screenshots/, real CSV files read back and asserted on, not
just described.
"""

import csv
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView

from app.settings_service import SettingsService
from app.widgets.incident_table import COLUMNS, IncidentTablePage
from core.detection.parsers import parse_csv, parse_json, parse_syslog
from data.db import connect
from data.models import Incident, IncidentCategory, IncidentStatus
from data.repositories.incident_repo import IncidentRepository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT_DIR = PROJECT_ROOT / "docs" / "screenshots"

SYSLOG_SAMPLE = """Jul 26 09:00:00 web01 sshd: Failed password for admin from 203.0.113.5
Jul 26 09:05:00 web01 kernel: critical hardware fault on disk sda
Jul 26 09:10:00 db02 cron: Notice: nightly backup completed
Jul 26 09:15:00 web01 sshd: Failed password for root from 203.0.113.9
"""

JSON_SAMPLE = (
    '{"timestamp": "2026-07-26T10:00:00", "severity": "high", "source": "fw01", '
    '"src_ip": "10.0.0.9", "category": "port_scan", "message": "port scan detected"}\n'
    '{"timestamp": "2026-07-26T10:05:00", "severity": "low", "source": "fw01", '
    '"message": "heartbeat ok"}\n'
)

CSV_SAMPLE = (
    "timestamp,severity,source,src_ip,category,message\n"
    "2026-07-26 11:00:00,critical,edge01,192.168.1.5,malware_execution,malware signature match\n"
    "2026-07-26 11:05:00,medium,edge01,,,unusual outbound volume\n"
)


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _seed_incidents(repo: IncidentRepository) -> list[Incident]:
    parsed = parse_syslog(SYSLOG_SAMPLE, year=2026) + parse_json(JSON_SAMPLE) + parse_csv(CSV_SAMPLE)
    return [repo.insert_incident(inc) for inc in parsed]


@pytest.fixture
def repo(tmp_path):
    conn = connect(tmp_path / "incidents.db")
    repository = IncidentRepository(conn)
    _seed_incidents(repository)
    return repository


@pytest.fixture
def settings(tmp_path):
    conn = connect(tmp_path / "settings.db")
    return SettingsService(connection=conn)


@pytest.fixture
def page(repo, settings, qapp):
    widget = IncidentTablePage(incident_repo=repo, settings_service=settings)
    widget.resize(1000, 500)
    yield widget
    widget.close()


# -- seeding sanity ---------------------------------------------------------


def test_seed_produced_incidents_from_all_three_parsers(repo):
    rows = repo.list_incident_rows()
    assert len(rows) == 8  # 4 syslog + 2 json + 2 csv

    # Category is now semantic (Task 5b), not the parser's format name —
    # 2 syslog lines infer BRUTE_FORCE from "Failed password"; the JSON and
    # CSV samples each explicitly name a category for one row and omit it
    # for the other (UNCATEGORIZED), and the 2 remaining syslog lines have
    # no category keyword at all (also UNCATEGORIZED).
    categories = {row.incident.category for row in rows}
    assert categories == {
        IncidentCategory.BRUTE_FORCE,
        IncidentCategory.PORT_SCAN,
        IncidentCategory.MALWARE_EXECUTION,
        IncidentCategory.UNCATEGORIZED,
    }


# -- column filtering + search, composable ----------------------------------


def _column_index(key: str) -> int:
    return next(i for i, (k, _label, _explain) in enumerate(COLUMNS) if k == key)


def test_column_filter_narrows_rows(page):
    source_col = _column_index("source")
    page.set_column_filter(source_col, "web01")
    assert page.proxy_model().rowCount() == 3  # 3 of the 4 syslog lines are host web01


def test_search_is_composable_with_column_filter(page):
    source_col = _column_index("source")
    page.set_column_filter(source_col, "web01")
    page.proxy_model().set_search_text("root")
    # of web01's 3 rows, only 1 description mentions "root"
    assert page.proxy_model().rowCount() == 1


def test_clearing_column_filter_restores_rows(page):
    source_col = _column_index("source")
    total = page.proxy_model().rowCount()
    page.set_column_filter(source_col, "web01")
    assert page.proxy_model().rowCount() < total
    page.set_column_filter(source_col, "")
    assert page.proxy_model().rowCount() == total


def test_fuzzy_search_suggests_close_match_on_zero_results(page, qapp):
    page.show()  # isVisible() reflects composed ancestor visibility too
    qapp.processEvents()

    # "syslog" no longer appears anywhere in visible data now that Category
    # is semantic (Task 5b) rather than the parser's format name — use a
    # word that's still genuinely present, from a description field.
    page._search_box.setText("passwrd")  # typo for "password"
    qapp.processEvents()
    assert page._suggestion_label.isVisible()
    assert "password" in page._suggestion_label.text().lower()


# -- sorting ------------------------------------------------------------


def test_sorting_by_severity_uses_rank_not_alphabetical(page):
    severity_col = _column_index("severity")
    page.table_view().sortByColumn(severity_col, Qt.SortOrder.AscendingOrder)

    proxy = page.proxy_model()
    severities_in_order = [
        proxy.data(proxy.index(r, severity_col), Qt.ItemDataRole.DisplayRole) for r in range(proxy.rowCount())
    ]
    # Critical must sort before High before Medium before Low — alphabetical
    # would put Critical, High, Low, Medium instead.
    rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    ranks = [rank[s] for s in severities_in_order]
    assert ranks == sorted(ranks)


# -- CSV export of the filtered/sorted view, not the full table -------------


def test_csv_export_respects_active_filter(page, tmp_path):
    source_col = _column_index("source")
    page.set_column_filter(source_col, "edge01")  # 2 of 8 rows

    out_path = tmp_path / "filtered.csv"
    page.export_filtered_csv(out_path)

    with open(out_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    header, *data_rows = rows
    assert header == [label for _key, label, _explain in COLUMNS]
    assert len(data_rows) == 2
    assert all(row[_column_index("source")] == "edge01" for row in data_rows)


def test_csv_export_respects_sort_order(page, tmp_path):
    severity_col = _column_index("severity")
    page.table_view().sortByColumn(severity_col, Qt.SortOrder.AscendingOrder)

    out_path = tmp_path / "sorted.csv"
    page.export_filtered_csv(out_path)

    with open(out_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    _header, *data_rows = rows
    rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    ranks = [rank[row[severity_col]] for row in data_rows]
    assert ranks == sorted(ranks)


# -- row context menu: status change -----------------------------------------


def test_apply_status_change_updates_current_status(page, repo):
    row = page.proxy_model().sourceModel().row_at(0)
    page.apply_status_change(row, IncidentStatus.INVESTIGATING, "checking this out")

    refreshed = repo.list_incident_rows()
    updated = next(r for r in refreshed if r.incident.id == row.incident.id)
    assert updated.status == IncidentStatus.INVESTIGATING
    assert updated.note == "checking this out"


def test_row_context_menu_offers_all_four_statuses(page):
    row = page.proxy_model().sourceModel().row_at(0)
    menu = page.build_row_context_menu(row)
    labels = {action.text() for action in menu.actions()}
    assert labels == {f"Mark {s.display_name}" for s in IncidentStatus}


# -- header context menu: filter + explain -----------------------------------


def test_header_context_menu_has_explain_action(page):
    col = _column_index("severity")
    menu = page.build_header_context_menu(col)
    labels = [action.text() for action in menu.actions()]
    assert any("Explain" in label for label in labels)
    assert any("Filter" in label for label in labels)


# -- persisted column widths --------------------------------------------------


def test_column_width_persists_across_new_page_instance(repo, settings, qapp):
    page1 = IncidentTablePage(incident_repo=repo, settings_service=settings)
    header = page1.table_view().horizontalHeader()
    col = _column_index("description")
    header.resizeSection(col, 321)
    page1._on_section_resized()  # resizeSection alone doesn't emit sectionResized
    page1.close()

    page2 = IncidentTablePage(incident_repo=repo, settings_service=settings)
    assert page2.table_view().horizontalHeader().sectionSize(col) == 321
    page2.close()


# -- real screenshots ---------------------------------------------------------


def test_screenshot_table_with_filter_and_sort_active(page, qapp):
    source_col = _column_index("source")
    page.set_column_filter(source_col, "web01")
    page.table_view().sortByColumn(_column_index("first_seen"), Qt.SortOrder.DescendingOrder)

    page.show()
    qapp.processEvents()

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCREENSHOT_DIR / "incident_table_filtered_sorted.png"
    assert page.grab().save(str(out_path))


def test_screenshot_header_context_menu(page, qapp):
    page.show()
    qapp.processEvents()

    menu = page.build_header_context_menu(_column_index("severity"))
    menu.show()
    qapp.processEvents()

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCREENSHOT_DIR / "incident_table_header_menu.png"
    assert menu.grab().save(str(out_path))
    menu.close()


def test_screenshot_row_context_menu(page, qapp):
    page.show()
    qapp.processEvents()

    row = page.proxy_model().sourceModel().row_at(0)
    menu = page.build_row_context_menu(row)
    menu.show()
    qapp.processEvents()

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCREENSHOT_DIR / "incident_table_row_menu.png"
    assert menu.grab().save(str(out_path))
    menu.close()
