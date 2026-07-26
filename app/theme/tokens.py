"""Design tokens — single source of truth for color in this app.

Nothing outside this file should hardcode a hex color. Qt widgets consume
these via generated QSS (later task); tests/theme/test_contrast.py checks
every pairing in PAIRINGS below and fails the build if any pairing is not
readable.

Two token families:

- Surface / Primary / Neutral / Accent: the brand palette. Free to change
  on a rebrand.
- Severity: functional status color (red/orange/yellow/green). EXEMPT
  from brand overrides — these carry fixed meaning (critical/high/medium/
  low) in the SOC domain and must not be restyled to match a brand refresh.
"""

from dataclasses import dataclass


class Surface:
    WHITE = "#FFFFFF"
    NEAR_WHITE = "#F7F8F7"
    RAISED = "#EEF0EE"


class Primary:
    BASE = "#1E4620"
    HOVER = "#173618"
    PRESSED = "#102610"
    ON_PRIMARY = "#FFFFFF"


class Neutral:
    """Ramp for fills and decoration. N500/N600/N700/N900 additionally
    back a semantic role below and are covered by the contrast test;
    N100-N400 are decorative fills only and are not text/boundary colors."""

    N100 = "#F2F2F1"
    N200 = "#E1E3E0"
    N300 = "#C7CAC6"
    N400 = "#9AA096"
    N500 = "#767C73"
    N600 = "#5F655D"
    N700 = "#33362F"
    N900 = "#1B1D19"

    BORDER = N500
    TEXT_MUTED = N600
    TEXT_PRIMARY = N700
    TEXT_HIGH_EMPHASIS = N900


class Accent:
    """Single accent — interactive highlight, links, focus rings. Kept
    distinct from Primary (brand chrome) and from Severity.LOW (status
    meaning), even though all three sit in the green family."""

    BASE = "#3F8F44"
    ON_ACCENT = "#FFFFFF"


class Severity:
    """Functional status color. Not brand-overridable."""

    CRITICAL = "#B3261E"
    HIGH = "#B3540A"
    MEDIUM = "#8A6D00"
    LOW = "#2E7D32"
    ON_SEVERITY = "#FFFFFF"


@dataclass(frozen=True)
class Pairing:
    label: str
    foreground: str
    background: str
    category: str  # "body" (4.5:1) or "large" (3:1 — large text / UI boundary)


# Every foreground/background combination actually used in the app.
# This is the registry the contrast test iterates over — not every
# mathematically possible token combination, only the ones the design
# intends to render together.
PAIRINGS: list[Pairing] = [
    # Body text on surfaces
    Pairing("body text on white surface", Neutral.TEXT_PRIMARY, Surface.WHITE, "body"),
    Pairing("body text on near-white surface", Neutral.TEXT_PRIMARY, Surface.NEAR_WHITE, "body"),
    Pairing("body text on raised surface", Neutral.TEXT_PRIMARY, Surface.RAISED, "body"),
    Pairing("high-emphasis text on white surface", Neutral.TEXT_HIGH_EMPHASIS, Surface.WHITE, "body"),
    Pairing("muted/secondary text on white surface", Neutral.TEXT_MUTED, Surface.WHITE, "body"),
    Pairing("muted/secondary text on raised surface", Neutral.TEXT_MUTED, Surface.RAISED, "body"),
    # Primary button in its three interaction states — button labels are
    # regular-weight body-sized text, so held to 4.5:1, not the looser 3:1.
    Pairing("primary button label (rest)", Primary.ON_PRIMARY, Primary.BASE, "body"),
    Pairing("primary button label (hover)", Primary.ON_PRIMARY, Primary.HOVER, "body"),
    Pairing("primary button label (pressed)", Primary.ON_PRIMARY, Primary.PRESSED, "body"),
    # Accent — used only for links/focus rings, i.e. large-scale or
    # non-text UI boundaries, never small body-text-on-accent.
    Pairing("accent link text on white surface", Accent.BASE, Surface.WHITE, "large"),
    Pairing("accent focus ring on white surface", Accent.BASE, Surface.WHITE, "large"),
    # Structural borders/dividers — non-text UI component boundary, 3:1.
    Pairing("border on white surface", Neutral.BORDER, Surface.WHITE, "large"),
    Pairing("border on raised surface", Neutral.BORDER, Surface.RAISED, "large"),
    # Severity badge labels — actual word ("Critical"/"High"/...), body 4.5:1.
    Pairing("critical badge label", Severity.ON_SEVERITY, Severity.CRITICAL, "body"),
    Pairing("high badge label", Severity.ON_SEVERITY, Severity.HIGH, "body"),
    Pairing("medium badge label", Severity.ON_SEVERITY, Severity.MEDIUM, "body"),
    Pairing("low badge label", Severity.ON_SEVERITY, Severity.LOW, "body"),
    # Severity dot/icon indicators with no adjacent text — non-text UI
    # boundary, 3:1.
    Pairing("critical severity dot on white", Severity.CRITICAL, Surface.WHITE, "large"),
    Pairing("high severity dot on white", Severity.HIGH, Surface.WHITE, "large"),
    Pairing("medium severity dot on white", Severity.MEDIUM, Surface.WHITE, "large"),
    Pairing("low severity dot on white", Severity.LOW, Surface.WHITE, "large"),
]
