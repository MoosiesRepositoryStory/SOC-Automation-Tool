"""Wraps ScanPipeline and emits a Qt signal per new rule match — the only
place a Qt signal touches pipeline results, keeping core/pipeline.py
itself Qt-free. Same wrapping pattern as SettingsService around
SettingsRepository.

A full notification system (toast, tray icon, sound, ...) isn't in scope
for Task 5d — the signal is deliberately as far as this goes for now.
"""

from PySide6.QtCore import QObject, Signal

from core.pipeline import RuleMatch, ScanPipeline, ScanResult


class AlertService(QObject):
    rule_matched = Signal(object)  # emits RuleMatch

    def __init__(self, pipeline: ScanPipeline, parent=None):
        super().__init__(parent)
        self._pipeline = pipeline

    def run_scan(self, text: str, source_format: str, source_path: str) -> ScanResult:
        result = self._pipeline.run(text, source_format, source_path)
        for match in result.matches:
            self.rule_matched.emit(match)
        return result
