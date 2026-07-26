"""Structural contrast gate.

Every foreground/background pairing declared in app/theme/tokens.py is
checked against its stated WCAG threshold. This must pass before any
screen is built against these tokens, and again in CI on every change to
tokens.py — the detail-panel regression from the prior build was caught by
eyeballing a screenshot, which is exactly the failure mode this replaces.

Threshold classification:
  - "body": normal text (labels, badge text, button labels) -> 4.5:1
  - "large": large-scale text, or a non-text UI boundary (borders, focus
    rings, status dots with no adjacent label) -> 3:1

Runs headless via QT_QPA_PLATFORM=offscreen, e.g.:
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/theme/
Task 4's nav-position tests will reuse this same headless pattern, so both
are CI-ready the same way.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.theme.contrast import contrast_ratio
from app.theme.tokens import PAIRINGS

THRESHOLDS = {
    "body": 4.5,
    "large": 3.0,
}


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Constructs a real QApplication under the offscreen platform plugin.

    Proves the headless Qt bootstrap itself works in this environment,
    not just that the contrast arithmetic is correct — if PySide6 or the
    offscreen plugin were missing, this fixture is where it would fail,
    loudly, before any assertion runs.
    """
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.parametrize("pairing", PAIRINGS, ids=lambda p: p.label)
def test_pairing_meets_wcag_threshold(pairing):
    ratio = contrast_ratio(pairing.foreground, pairing.background)
    required = THRESHOLDS[pairing.category]
    assert ratio >= required, (
        f"{pairing.label}: {pairing.foreground} on {pairing.background} "
        f"= {ratio:.2f}:1, needs >= {required}:1 ({pairing.category} text/boundary)"
    )


def test_registry_covers_every_defined_severity_and_surface():
    labels = {p.label for p in PAIRINGS}
    assert any("critical" in l for l in labels)
    assert any("high" in l for l in labels)
    assert any("medium" in l for l in labels)
    assert any("low" in l for l in labels)
    assert any("white surface" in l for l in labels)
    assert any("raised surface" in l for l in labels)
