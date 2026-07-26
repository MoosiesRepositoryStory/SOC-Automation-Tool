# Architecture Decisions

Status: **accepted, pre-implementation.** Written before any UI work.
Environment findings that constrain these decisions are in `../CLAUDE.md`.

---

## 1. Module boundaries

The prior build's separation — GUI calls a pipeline class's `run` method,
never reimplements detection inline — was the part that worked. It is
carried forward and made enforceable.

```
soc_tool/
  app/                  # Qt lives here and ONLY here
    main.py             # entry point, QApplication, fade_in_window()
    main_window.py      # nav-region grid + QStackedWidget content
    nav/                # NavRail, NavPosition (Task 4)
    pages/              # dashboard, incidents, scans, settings, about
    widgets/            # copyable table, detail panel, log console (Task 6)
    theme/              # tokens.py + QSS generation (Task 2)
    workers.py          # QThread wrappers around core; the ONLY bridge
  core/                 # pure logic — zero Qt imports
    pipeline.py         # ScanPipeline.run() -> ScanResult
    detection/          # rules, parsers, normalizers
    enrichment/         # geo/ASN/WHOIS clients + cache policy
    diffing.py          # scan-to-scan diff
    metrics.py          # false-positive rate, trend aggregation
    mitre.py            # ATT&CK technique map (verified IDs only)
  data/                 # persistence — zero Qt imports
    paths.py            # XDG / platform-aware path resolution
    db.py               # connection, WAL, migrations
    models.py           # dataclasses crossing the boundary
    repositories/       # incident_repo, scan_repo, settings_repo, rule_repo
  packaging/            # .deb tree, .desktop, icons, build scripts
  tests/
```

**The dependency rule:** `app/` → `core/` → `data/`. Never upward.
`core/` and `data/` must not import PySide6.

**Enforced, not trusted.** A test walks the AST of every module under
`core/` and `data/` and fails on any `PySide6` import. Layering that
depends on remembering is layering that erodes; this is cheap insurance and
it is the reason the prior separation is worth reproducing rather than
merely intending.

**Crossing the boundary without leaking Qt.** The GUI must not block, but
`core/` cannot emit Qt signals. So:

```python
# core/pipeline.py  — no Qt
def run(self,
        on_progress: Callable[[Progress], None] | None = None,
        cancel: threading.Event | None = None) -> ScanResult: ...
```

`app/workers.py` wraps that in a `QThread`, passes a callback that
re-emits as a Qt signal, and owns a `threading.Event` for cancellation.
Plain callables and `threading.Event` are stdlib, so `core/` stays testable
headless with no Qt at all. Cancellation is cooperative — checked between
pipeline stages, never a thread kill.

**Data crossing the boundary is dataclasses, not `sqlite3.Row`.**
Repositories return `Incident`, `Scan`, `AlertRule`. The GUI never sees SQL
and never sees a tuple whose column order it has to know.

---

## 2. Persistence — SQLite

**Decision: SQLite, stdlib `sqlite3`, WAL mode.** Three of the backlog
features (status tracking, scan history, false-positive rate) are
queryable-history features. A JSON/flat file cannot answer "FP rate over
the last 30 days by category" without loading and re-deriving everything.
SQLite is single-file, serverless, ships with Python, and single-user
desktop concurrency is well within its envelope.

WAL mode so the UI can read while a scan writes.

### The one schema decision that matters

**Incident status is an append-only history table, not a mutable column.**

```sql
incidents(id, scan_id, first_seen, last_seen, category, severity,
          src_ip, dst_ip, ...)              -- current status is DERIVED
incident_status_history(id, incident_id, status, note, changed_at,
                        changed_by, prev_status)
```

Current status = latest row for that incident. This is not
over-engineering; three separate requirements collapse into it:

- **False-positive rate over time** is impossible from a mutable column.
  Overwriting `status` destroys the very series the metric plots. This is
  exactly the class of error the brief calls out — it would be *silently*
  wrong: the number renders, looks plausible, and is not recoverable after
  the fact because the history was never kept.
- **Undo on status change** (a Task 7 candidate) is `prev_status`, free.
- **Audit** — "who marked this a false positive, when, and why" is the
  question a SOC tool exists to answer.

Storing the current status as a denormalized column *in addition*, kept in
sync by trigger, is a legitimate later optimization. It is not the source
of truth.

Other tables: `scans`, `alert_rules`, `enrichment_cache` (with
`fetched_at` for TTL and negative-result caching so a failed WHOIS is not
retried on every render), `settings`.

**Migrations:** `PRAGMA user_version` + an ordered list of migration
functions, applied on startup inside a transaction. No migration framework
dependency for a schema this size.

**Location** via `data/paths.py`:

| | Linux | Windows (later) |
|---|---|---|
| DB | `$XDG_DATA_HOME/soc-tool/soc.db` → `~/.local/share/...` | `%LOCALAPPDATA%` |
| Config | `$XDG_CONFIG_HOME/soc-tool/` | `%APPDATA%` |
| Cache | `$XDG_CACHE_HOME/soc-tool/` | `%LOCALAPPDATA%\...\Cache` |

Written platform-aware on day one. An AppImage mounts read-only and a
Windows build has no `~/.local` — both break on a hardcoded path, and both
break *late*, at packaging time, when it is most expensive to unpick.

---

## 3. Packaging

**Primary: `.deb` bundling a venv under `/opt/soc-tool`.**
**Secondary: AppImage, later, if distribution goes beyond the Debian family.**

The reasoning is specific to what was found on this machine:

- PySide6 **is not in the Ubuntu noble repos**, so a `.deb` cannot declare
  it via `Depends:`. The package must therefore vendor its own venv —
  `/opt/soc-tool/venv` plus a launcher on `PATH`. This is normal practice
  for Python desktop apps and it removes any interaction with the system
  Python.
- `dpkg-deb` is already present; `appimagetool` and `fuse2fs` are not, and
  AppImage's FUSE requirement on 24.04 needs `libfuse2` which is not
  installed by default. AppImage costs more setup for a portability
  benefit not yet needed.
- `.deb` gets correct desktop integration free: `.desktop` into
  `/usr/share/applications/`, icons into
  `/usr/share/icons/hicolor/<size>/apps/`. That is the delivery mechanism
  Task 3 depends on.

Package layout:

```
/opt/soc-tool/venv/            bundled interpreter deps (PySide6)
/opt/soc-tool/soc_tool/        application
/usr/bin/soc-tool              launcher shim
/usr/share/applications/soc-tool.desktop
/usr/share/icons/hicolor/{16x16,32x32,64x64,256x256}/apps/soc-tool.png
/usr/share/icons/hicolor/scalable/apps/soc-tool.svg
```

### Windows / PyInstaller — what it would need later

Not built now; recorded so the decisions above stay compatible.

- `--windowed` (no console), and **hidden imports / Qt plugin bundling** —
  PyInstaller routinely misses `PySide6` platform plugins; the
  `platforms/qwindows.dll` omission is the classic silent-failure mode.
- **Icon format differs.** Windows needs a real multi-resolution `.ico`.
  The SVG source of truth (Task 3) makes this a render step, not a redraw.
- **Taskbar identity has no WM_CLASS analog.** Windows groups by
  `AppUserModelID`, set via `SetCurrentProcessExplicitAppUserModelID`.
  The Linux approach in Task 3 does not carry over — this is called out
  in the brief and it is correct.
- **Paths** — handled already if `paths.py` is respected. This is the item
  most likely to be quietly violated between now and then.

---

## 4. State management for the modular dashboard position (Task 4)

Nav-rail placement is a **first-class layout setting**, designed in now.

**Where it lives.** A `settings` table in SQLite, behind a `SettingsService`
that emits a Qt signal on change (the service is in `app/`, the repository
in `data/`). **Not `QSettings`** — `QSettings` is the more idiomatic Qt
answer, and it is rejected deliberately: it splits user state across two
stores with two backup stories and two migration stories. Nav position is
user data, and one queryable file is worth more here than idiom.

**How the layout works.** The central widget is a `QGridLayout` with the
content `QStackedWidget` fixed at cell (1,1) and the rail re-parented into
one of the four surrounding cells:

```
        (0,1) TOP
(1,0) LEFT   [content]   (1,2) RIGHT
        (2,1) BOTTOM
```

Changing position = remove the rail from the grid, re-add at the new cell,
call `rail.set_orientation(...)`. No window teardown.

**`QDockWidget` is rejected.** It looks like the built-in answer and it is
the wrong one: it drags in floating, closable, and drag-to-redock behaviour
that is not wanted, and its position persistence is an opaque
`saveState()` blob that cannot be inspected, migrated, or asserted against
in a test. An explicit enum plus an explicit grid cell can be.

**Four real orientations, not one rotated layout.** The brief is explicit
and it is right. `NavRail.set_orientation()` rebuilds its items:

- **Vertical (left/right):** icon above label, items stacked in a column,
  fixed comfortable width, labels wrap.
- **Horizontal (top/bottom):** icon beside label, items in a row, fixed
  short height, labels truncate with elision rather than wrap.

These are different widgets internally. Rotating the vertical layout gives
a tall top bar with stacked text — the failure mode worth naming, since it
is the one that looks done in a screenshot and is wrong in use.

**Interaction with the animation constraints.** Page transitions crossfade
at the page level (a `QGraphicsOpacityEffect` on the page widget is fine —
it is not the top-level window, and not nested inside an animating parent).
The window fade uses `windowOpacity`. **A nav-position change is not
animated at all** — it is a re-layout of the animating parent, which is
precisely the second historical bug. Rebuild, do not fade.

**Testable.** Under `QT_QPA_PLATFORM=offscreen`: set each of the four
positions, assert the rail's grid cell and its orientation mode, and
capture a screenshot per orientation. Same headless path CI uses for the
Task 2 contrast test.

---

## Open questions

1. **Scan input source.** The pipeline's contract is settled; what it
   *ingests* (log files, live capture, an API) is not specified in the
   brief and shapes `core/detection/`. Needed before Task 5.
2. **Enrichment providers.** Geo/ASN/WHOIS provider choice affects rate
   limits, API keys in settings, and offline behaviour.
3. **Multi-user / shared DB.** Assumed single-user local. If two analysts
   ever share a DB, `changed_by` in the status history is already there,
   but WAL-on-network-filesystem is not safe and this would need revisiting.
