# SOC Automation Tool

Desktop SOC triage/automation tool. **Full rebuild** of a prior
Windows/PyQt project that reached near-completion and was lost to a machine
change with no persisted memory. The code is new; the decisions and the
scar tissue below are carried forward. Keep this file current — it exists
so a session or machine change never costs the project again.

---

## Environment (verified 2026-07-26 on this machine)

| Item | State |
|---|---|
| OS | Linux Mint 22.3 "Zena" (Ubuntu 24.04 "noble" base) |
| Session | X11, Cinnamon (`XDG_CURRENT_DESKTOP=X-Cinnamon`) |
| Python | 3.12.3, system `/usr/bin/python3` |
| `python3-venv` / `python3-pip` | Installed during Task 1 follow-up; `.venv/` created at project root |
| PySide6 | **Not in apt repos on noble** — installed via pip into `.venv` (6.11.1) |
| PyQt6 | In apt (`6.6.1-2build4`), not installed |
| `libxcb-cursor0` | **NOT installed** — Qt's `xcb` platform plugin cannot load without it; **no real PySide6 window can open on this X11 session at all** until this is installed. Found during Task 3 (WM_CLASS check crashed with `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`). `QT_QPA_PLATFORM=offscreen` is unaffected — all headless tests still pass. Fix: `sudo apt install libxcb-cursor0` |
| `dpkg-deb` | Present |
| `appimagetool`, `fuse2fs` | Absent |

Bootstrap (needs sudo, one time):

```bash
sudo apt install python3-venv python3-pip
python3 -m venv .venv && .venv/bin/pip install -U pip
.venv/bin/pip install PySide6
```

## Tech stack decisions

- **Qt binding: PySide6.** LGPL — no commercial-license question. The
  tradeoff on this machine is that it is pip-only (PyQt6 is the apt-easy
  one), which is precisely the licensing complexity we are paying a little
  setup friction to avoid. Do not switch to PyQt6 for convenience without
  revisiting the license question deliberately.
- **Persistence: SQLite** (stdlib `sqlite3`, WAL mode). Status tracking,
  scan history, and false-positive-rate metrics are all queryable-history
  features; a flat file cannot serve them.
- **Packaging: `.deb` primary** (bundled venv under `/opt`), AppImage
  secondary. Rationale and the Windows/PyInstaller notes are in
  `docs/architecture.md`.
- **Paths: XDG from day one** via a single `paths.py`. Never hardcode —
  a Windows build later and an AppImage's read-only mount both break on
  hardcoded paths.

## Hard constraints — do not relearn these the hard way

### Qt animation (two bugs from the prior build)

1. **Top-level window fades use `windowOpacity`** via a `fade_in_window()`
   helper. **Never** `QGraphicsOpacityEffect` on a top-level window.
2. **Page/child widgets crossfade at their own level.** Never nest a
   `QGraphicsEffect` inside an already-animating parent. When the nav rail
   changes position (see Task 4), rebuild the layout — do not animate it
   with an effect on the parent.

### Contrast (the detail-panel regression)

Last build shipped a detail panel whose value text was nearly invisible
against its own background. The fix is **structural, not cosmetic**: every
foreground/background token pairing is checked for WCAG ratio by an
automated test that fails the build below 4.5:1 (body) / 3:1 (large text
and UI boundaries). That test runs before any screen is built on the
tokens, and in CI on every change to the token file. Fixing contrast by
eyeballing a screenshot is not acceptable here — it is what failed before.

### Layering

`core/` and `data/` must never import Qt. Enforced by an import-guard test,
not by discipline. The GUI calls `ScanPipeline.run()`; it never
reimplements detection logic inline. This mirrors the prior project's
separation, which was the part that worked.

### Copy-paste (Task 6)

Every text-bearing surface — table cells, detail panels, scan log console —
supports text selection and Ctrl+C. This is a full sweep across all
widgets, not a per-panel fix as issues are noticed.

## Feature backlog (Task 5 — consolidated, not re-invented)

- Status workflow: New / Investigating / Resolved / False Positive, + notes
- Column filtering + sorting, composable with search
- CSV export of the **current filtered view**
- MITRE ATT&CK mapping per incident category — **verify real technique IDs
  against attack.mitre.org; never fabricate a mapping**
- Timeline/trend chart, severity-broken-down, 7-day default
- Configurable alerting rules (AND-combinable condition builder) — test
  zero-match and overlapping-rule cases explicitly
- IP/asset enrichment (geolocation, ASN, WHOIS), locally cached, graceful
  failure, behind a Settings toggle
- Scan diffing (new / resolved / changed-field) — test reappearing-ID and
  field-only-changed edge cases explicitly
- False-positive rate tracking — **formula shown to the user**, manually
  verified against known-status incidents before being called done. A wrong
  statistic here is worse than no statistic.
- Right-click context menus (row-level; column-header "explain this
  field"), Ctrl+F fuzzy search with "did you mean", persisted column widths

## Working agreement

- Report after each task with a screenshot for anything visual. Verify
  before moving on; do not batch silently.
- Task 7's ease-of-access list is **flagged for approval before
  implementation** — do not build it silently.

---

## Model routing

Default: Sonnet 5. Escalate to Opus 4.8 only for architecture/design
decisions with real ambiguity, and any statistic or calculation whose wrong
answer would be **silently wrong rather than loudly broken**. Never
Fable/Mythos for this project — it is priced for frontier-depth strategy
work this project does not need.

Switch manually with `/model` (or `opusplan` for plan-shaped work). **Claude
Code will not switch on its own from reading this file** — this is a
reference for the operator, not an enforced directive. Run `/status` if
unsure what is loaded, especially after long sessions; plan-mode sessions
have been known to silently downgrade past ~200K tokens.

| Task | Model | Effort |
|---|---|---|
| 1 — Architecture Decisions Document | Opus 4.8 (`opusplan` fits) | high |
| 2 — Design System, contrast-safe | Sonnet 5 | default |
| 3 — Logo | Sonnet 5 | default |
| 4 — Modular Dashboard Position | Sonnet 5 | default |
| 5 — Feature Set | Sonnet 5 | default* |
| 6 — Copy-Pasteable Content | Sonnet 5 | default |
| 7 — Ease-of-Access Review | Sonnet 5 | high |

\* Task 5 exceptions: chart / alerting / enrichment / diffing sub-items →
effort high. **False-positive-rate tracking → Opus 4.8 + high**, switched
just for that sub-item, then back to Sonnet.
