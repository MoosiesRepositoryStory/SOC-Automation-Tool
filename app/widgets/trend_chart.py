"""Timeline/trend chart — incident counts per day, broken down by
severity. Default range: last 7 days.

Severity colors come from app/theme/tokens.py's Severity class (the same
contrast-tested tokens from Task 2) — QtCharts' own default palette is
never used, so a charting library can't quietly reintroduce untested
colors into the design system.
"""

from datetime import date, datetime, timedelta

from PySide6.QtCharts import QBarCategoryAxis, QChart, QChartView, QBarSet, QStackedBarSeries, QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from app.theme.tokens import Severity as SeverityTokens
from data.models import Severity

_SEVERITY_ORDER = (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW)

_SEVERITY_COLOR = {
    Severity.CRITICAL: SeverityTokens.CRITICAL,
    Severity.HIGH: SeverityTokens.HIGH,
    Severity.MEDIUM: SeverityTokens.MEDIUM,
    Severity.LOW: SeverityTokens.LOW,
}

# (label, days) -- index 0 is the default.
_RANGE_OPTIONS: list[tuple[str, int]] = [
    ("Last 7 Days", 7),
    ("Last 14 Days", 14),
    ("Last 30 Days", 30),
    ("Last 90 Days", 90),
]

EMPTY_STATE_MESSAGE = "No incidents recorded in the selected range."


class TrendChartPage(QWidget):
    def __init__(self, incident_repo, parent: QWidget | None = None):
        super().__init__(parent)
        self._repo = incident_repo
        self._last_counts: dict[date, dict[Severity, int]] = {}

        self._range_combo = QComboBox()
        for label, _days in _RANGE_OPTIONS:
            self._range_combo.addItem(label)
        self._range_combo.currentIndexChanged.connect(self._on_range_changed)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Range:"))
        top_bar.addWidget(self._range_combo)
        top_bar.addStretch(1)

        self._empty_label = QLabel(EMPTY_STATE_MESSAGE)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._chart_view = QChartView()
        self._chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._chart_view)  # index 0
        self._stack.addWidget(self._empty_label)  # index 1

        layout = QVBoxLayout(self)
        layout.addLayout(top_bar)
        layout.addWidget(self._stack)

        self.refresh()

    # -- range control ------------------------------------------------------

    def selected_days(self) -> int:
        return _RANGE_OPTIONS[self._range_combo.currentIndex()][1]

    def set_selected_days(self, days: int) -> None:
        for index, (_label, option_days) in enumerate(_RANGE_OPTIONS):
            if option_days == days:
                self._range_combo.setCurrentIndex(index)
                return
        raise ValueError(f"{days} is not one of the available range options")

    def _on_range_changed(self, _index: int) -> None:
        self.refresh()

    # -- data + chart building ------------------------------------------------

    def refresh(self) -> None:
        days = self.selected_days()
        since = (datetime.now() - timedelta(days=days - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        counts = self._repo.count_by_day_and_severity(since)
        self._last_counts = counts

        total = sum(sum(day_counts.values()) for day_counts in counts.values())
        if total == 0:
            self._stack.setCurrentWidget(self._empty_label)
            return

        self._chart_view.setChart(self._build_chart(counts, days))
        self._stack.setCurrentWidget(self._chart_view)

    def is_showing_empty_state(self) -> bool:
        return self._stack.currentWidget() is self._empty_label

    def current_chart(self) -> QChart | None:
        return None if self.is_showing_empty_state() else self._chart_view.chart()

    def last_counts(self) -> dict[date, dict[Severity, int]]:
        return self._last_counts

    @staticmethod
    def _days_in_range(days: int) -> list[date]:
        today = date.today()
        return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]

    def _build_chart(self, counts: dict[date, dict[Severity, int]], days: int) -> QChart:
        all_days = self._days_in_range(days)

        series = QStackedBarSeries()
        for severity in _SEVERITY_ORDER:
            bar_set = QBarSet(severity.value.capitalize())
            bar_set.setColor(QColor(_SEVERITY_COLOR[severity]))
            for day in all_days:
                bar_set.append(counts.get(day, {}).get(severity, 0))
            series.append(bar_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(f"Incidents — last {days} days")
        chart.legend().setVisible(True)

        axis_x = QBarCategoryAxis()
        axis_x.append([d.strftime("%b %d") for d in all_days])
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        max_total = max((sum(counts.get(d, {}).values()) for d in all_days), default=1)
        axis_y = QValueAxis()
        axis_y.setRange(0, max(max_total, 1))
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        return chart
