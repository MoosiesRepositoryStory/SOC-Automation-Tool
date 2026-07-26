"""app/widgets/trend_chart.py — timeline/severity chart (Task 5c).

Same offscreen pattern as other widget tests. Asserts against the chart's
actual QBarSet values (not just "it rendered"), the empty-data path
explicitly (the real state of a fresh install), and that bar colors are
exactly the app/theme/tokens.py Severity values, not QtCharts' defaults.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from app.theme.tokens import Severity as SeverityTokens
from app.widgets.trend_chart import EMPTY_STATE_MESSAGE, TrendChartPage
from data.db import connect
from data.models import Incident, IncidentCategory, Severity
from data.repositories.incident_repo import IncidentRepository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT_DIR = PROJECT_ROOT / "docs" / "screenshots"


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def repo(tmp_path):
    conn = connect(tmp_path / "trend.db")
    return IncidentRepository(conn)


def _insert(repo, first_seen, severity):
    repo.insert_incident(
        Incident(
            id=None,
            scan_id=None,
            first_seen=first_seen,
            last_seen=first_seen,
            category=IncidentCategory.UNCATEGORIZED,
            severity=severity,
            source="test",
            src_ip=None,
            dst_ip=None,
            description="x",
            raw="x",
        )
    )


def _bar_set_by_label(chart, label):
    series = chart.series()[0]
    for bar_set in series.barSets():
        if bar_set.label() == label:
            return bar_set
    raise KeyError(label)


# -- empty-data path: the real state of a fresh install ----------------------


def test_empty_repo_shows_empty_state(repo, qapp):
    page = TrendChartPage(incident_repo=repo)
    assert page.is_showing_empty_state() is True
    assert page.current_chart() is None
    page.close()


def test_empty_state_message_is_visible_and_real(repo, qapp):
    page = TrendChartPage(incident_repo=repo)
    page.show()
    qapp.processEvents()
    assert page._empty_label.isVisible()
    assert page._empty_label.text() == EMPTY_STATE_MESSAGE
    page.close()


# -- seeded data: actual series values, not just "it rendered" ---------------


def test_chart_series_matches_seeded_counts_per_day_per_severity(repo, qapp):
    now = datetime.now()
    today = now.replace(hour=12, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    _insert(repo, today, Severity.CRITICAL)
    _insert(repo, today, Severity.HIGH)
    _insert(repo, yesterday, Severity.HIGH)
    _insert(repo, yesterday, Severity.HIGH)

    page = TrendChartPage(incident_repo=repo)
    assert page.is_showing_empty_state() is False

    chart = page.current_chart()
    assert chart is not None

    days = page._days_in_range(page.selected_days())
    today_index = days.index(today.date())
    yesterday_index = days.index(yesterday.date())

    critical_set = _bar_set_by_label(chart, "Critical")
    high_set = _bar_set_by_label(chart, "High")
    low_set = _bar_set_by_label(chart, "Low")

    assert critical_set.at(today_index) == 1
    assert critical_set.at(yesterday_index) == 0
    assert high_set.at(today_index) == 1
    assert high_set.at(yesterday_index) == 2
    assert low_set.at(today_index) == 0  # zero-filled, not absent from the axis
    page.close()


def test_chart_defaults_to_seven_day_range(repo, qapp):
    page = TrendChartPage(incident_repo=repo)
    assert page.selected_days() == 7
    page.close()


def test_range_dropdown_switches_to_fourteen_days(repo, qapp):
    now = datetime.now()
    ten_days_ago = now - timedelta(days=10)
    _insert(repo, ten_days_ago, Severity.MEDIUM)

    page = TrendChartPage(incident_repo=repo)
    assert page.is_showing_empty_state() is True  # 10 days ago is outside the 7-day default

    page.set_selected_days(14)
    assert page.is_showing_empty_state() is False

    chart = page.current_chart()
    medium_set = _bar_set_by_label(chart, "Medium")
    days = page._days_in_range(14)
    assert medium_set.at(days.index(ten_days_ago.date())) == 1
    page.close()


# -- colors come from tokens, not the charting library's defaults -----------


def test_bar_colors_match_severity_tokens_exactly(repo, qapp):
    now = datetime.now()
    for severity in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW):
        _insert(repo, now, severity)

    page = TrendChartPage(incident_repo=repo)
    chart = page.current_chart()

    expected = {
        "Critical": SeverityTokens.CRITICAL,
        "High": SeverityTokens.HIGH,
        "Medium": SeverityTokens.MEDIUM,
        "Low": SeverityTokens.LOW,
    }
    for label, token_hex in expected.items():
        bar_set = _bar_set_by_label(chart, label)
        assert bar_set.color() == QColor(token_hex), f"{label}: {bar_set.color().name()} != {token_hex}"
    page.close()


# -- real screenshots ---------------------------------------------------------


def test_screenshot_chart_with_seeded_data(repo, qapp):
    now = datetime.now()
    _insert(repo, now, Severity.CRITICAL)
    _insert(repo, now, Severity.CRITICAL)
    _insert(repo, now - timedelta(days=1), Severity.HIGH)
    _insert(repo, now - timedelta(days=1), Severity.MEDIUM)
    _insert(repo, now - timedelta(days=2), Severity.LOW)
    _insert(repo, now - timedelta(days=3), Severity.MEDIUM)
    _insert(repo, now - timedelta(days=3), Severity.MEDIUM)

    page = TrendChartPage(incident_repo=repo)
    page.resize(760, 480)
    page.show()
    qapp.processEvents()

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCREENSHOT_DIR / "trend_chart_seeded.png"
    assert page.grab().save(str(out_path))
    page.close()


def test_screenshot_empty_state(repo, qapp):
    page = TrendChartPage(incident_repo=repo)
    page.resize(760, 480)
    page.show()
    qapp.processEvents()

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCREENSHOT_DIR / "trend_chart_empty.png"
    assert page.grab().save(str(out_path))
    page.close()
