# KRT-120 visible-first theme switching

Reference record, 2026-10-31. KRT-120 remains In Progress. The owner authorized a
local commit using the recorded verification; native interactive acceptance is
pending. Git and Linear record the delivery state.

[source-manifest.json](source-manifest.json) records the final formatted source
and fixture hashes plus Python/Qt versions for this uncommitted batch.

## Owner-approved behavior

The problem is the delay after Settings Apply/OK until the selected theme appears.
The owner approved updating Settings first, then the workspace over subsequent
frames. Hidden panels may update when next shown, before presenting their content.
The initial bounded pass remains in place; its provisional historical evidence is
retained in [bounded-pass.md](bounded-pass.md) and [benchmark.json](benchmark.json).

## Implementation and contracts

- The global application stylesheet retains fixed geometry. A private compiler
  separates existing color/variable-font declarations from fixed metrics and
  rejects unsupported theme dependencies. Shipped themes and semantic roles
  remain the source of colors. Switching leaves the global metrics sheet intact.
- Feature panels, windows and tab/menu chrome own bounded color scopes. Local
  styles retain their overrides, including declaration-only stylesheets.
- Presentation subscriptions collect the latest theme. Settings receives its
  callbacks and colors first. After its paint, a widget-owned timer leaves one
  frame before continuing through visible scopes. A 250 ms fallback prevents
  occluded windows from stranding work. OK releases that wait when Settings hides.
- Replaced generations cancel older queued work. Hidden subscribers coalesce
  updates and flush on Show before paint. Newly introduced scopes receive the
  current theme. Widget styling stays on the GUI thread. QObject ownership
  explicitly bypasses item models' `parent(index)` overload.
- A graph is covered with its current themed background until the matching
  page/theme revision acknowledges two browser animation frames. Recoloring
  preserves positions, selection, camera, filters, lexicon overrides and physics.
  There is no theme-triggered page reload or content regeneration.
- Longform retains its cached rendered body and HTML installation cost. Themes
  preserve selection, scroll and navigation without Markdown conversion. Rich/
  source authoring document layout refreshes remain intact.
- Earlier duplicate-control cleanup, coalesced button geometry and bounded copied
  SVG cache remain. Effective-theme lookup excludes credentials; Settings
  persistence and world/local precedence are unchanged.

Authoring contracts 2/4/5/6/7/8/9 and action-label contract 11 apply. Visible routes,
keyboard ownership, exact authored text, drafts/dirty state, caret, selection,
undo/redo, playhead and navigation remain authoritative. No settings/schema
migration, version change or application restart is required.

Touched legacy presentation now uses `entity_main`/`event_main` for Explorer
identity and full-opacity `supporting_caption` for raster legend captions/ticks.
Raster gradient defaults come from the authored-data ColorMap default. These are
semantic corrections, not a claim of identical legacy pixels. Sixteen obsolete
exact visual-policy exceptions were removed across both passes; no new allowance
or baseline regeneration was used. No reviewed C901 hotspot changed. Forty
affected Help source reviews explain why existing controls and explanations
remain accurate; Help destinations and prose are unchanged.

## Settings-isolation correction

Earlier standalone probes used `setDefaultFormat(IniFormat)` with named QSettings
constructors. A fresh Windows check proved those still selected NativeFormat/
registry storage. Their isolation claim is withdrawn. An earlier Apply probe may
have changed the local default-theme preference; no prior value was guessed or
restored. No world/database was opened.

Current diagnostic children install `scripts/gui_probe_settings.py` before project
Qt imports. It forces explicit temporary INI stores, verifies format/resolved path,
disables fallbacks, rejects unsupported overloads and disables credential access.
Fixtures are disposable/generated. A subprocess regression checks isolation.

## Apply/OK first-result measurements

A hydrated generated Entity editor lives in a 960 x 900 main window beside the
real SettingsCoordinator/Settings Center. QTest clicks Apply or OK. Each variant
uses three fresh processes, two warm-ups and ten measured switches cycling all
six themes. Legacy/scoped variants share current code and fixtures; `legacy`
disables the new runtime, measuring improvement over the earlier bounded pass.

First result means verified current-theme pixels in Settings for Apply, or the
workspace for OK; the scope generation must also be current. Complete-frame time
includes the remaining queue, Qt layout/paint draining and pixel verification of
the window, editor input and visible Settings. These are separate metrics.

Python 3.13.14 / PySide6 and Qt 6.10.1, Windows offscreen Qt, Segoe UI. No concurrent
tests/render jobs, profiler or event counter ran during timing. P95 is nearest-rank
across the 30 retained samples per variant/route.

| Route/metric | Legacy median | Scoped median | Legacy p95 | Scoped p95 |
| --- | ---: | ---: | ---: | ---: |
| Apply: first Settings result | 938 ms | 94 ms | 961 ms | 98 ms |
| Apply: complete frame | 996 ms | 384 ms | 1,018 ms | 400 ms |
| OK: first workspace result | 963 ms | 322 ms | 976 ms | 335 ms |
| OK: complete frame | 1,012 ms | 383 ms | 1,032 ms | 394 ms |

Raw samples: [Apply legacy](apply-legacy.json), [Apply scoped](apply-scoped.json),
[OK legacy](ok-legacy.json), [OK scoped](ok-scoped.json).

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.venv/Scripts/python.exe -m scripts.benchmark_theme_apply `
  --presentation scoped --button apply --output tmp/theme-apply.json
```

Use `--presentation legacy` and `--button ok` for the matched alternatives.
Offscreen frames do not measure compositor scanout or human perception.

A separate native Windows Qt cross-check used the scoped runtime at 150% Qt
scaling, one fresh process per route, two warm-ups and ten samples. First verified
result medians were 111 ms for Apply and 368 ms for OK (p95 115/373 ms); complete
frames were 445/446 ms (p95 449/452 ms). Raw samples:
[native Apply](native-apply-scoped.json), [native OK](native-ok-scoped.json).
This smaller cross-check is not a matched native baseline or compositor/flicker
acceptance and does not replace the three-process offscreen comparison.

## Full settled-work fixture

The final matched comparison against immutable revision
`485706ecef32bd9879223b271c8696bc4a706b46` passes the automated performance gate:
at least 30% lower median editor/settings settled latency, with no greater than
10% p95 regression in either scenario. Raw samples and per-process counters:
[visible-first-benchmark.json](visible-first-benchmark.json).

| Scenario | Baseline median settled | Current median settled | Reduction | Baseline p95 | Current p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Editors/Settings | 2.321 s | 0.820 s | 64.66% | 2.364 s | 0.840 s |
| Loaded fixture | 2.575 s | 0.567 s | 77.98% | 2.665 s | 0.591 s |

Synchronous medians are 2.074 -> 0.080 s and 2.129 -> 0.334 s, respectively.
The editor/Settings queue continues after synchronous return and is fully
included in settled latency. P95 improves by 64.49% and 77.81%.

Separate instrumented-switch counters from the first process of each variant:

| Operation | Editors baseline/current | Loaded baseline/current |
| --- | ---: | ---: |
| Stylesheet assignments | 598 / 201 | 608 / 151 |
| Geometry notifications | 14,632 / 1,332 | 14,889 / 992 |
| SVG renders | 72 / 0 | 77 / 0 |
| Graph page reloads | 0 / 0 | 1 / 0 |
| Markdown conversions | 0 / 0 | 40 / 0 |
| HTML installations | 1 / 0 | 3 / 1 |

Longform's HTML installation is retained. Additional intermediate Qt paints in
the editor scenario are expected from visible-first presentation and count toward
settled timing; they are not excluded as deferred work.

Both variants use explicit temporary INI settings, matching generated fixtures,
Qt/fonts and 960 x 720 panel allocations. Entity/Event editors and Settings form
one scenario. The loaded scenario adds 100 timeline events, a 60-node/59-edge
graph and 40 Longform chapters, including previously opened hidden panels. This
is a multi-window widget fixture, not every production coordinator or world size.

Two warm-ups and ten alternating Dark/Light samples run in three fresh processes
per variant/scenario. Baseline overlays include changed package initializers and
unchanged package search paths. Settling waits for queued scopes, stable Qt
geometry/paint, real graph readiness, current theme acknowledgement and browser
frames. A separate instrumented switch counts stylesheet assignments, geometry
notifications, SVG renders, page reloads and Markdown conversions.

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:QTWEBENGINE_CHROMIUM_FLAGS = "--disable-gpu"
.venv/Scripts/python.exe -m scripts.benchmark_theme_switch `
  --baseline-ref 485706ecef32bd9879223b271c8696bc4a706b46 `
  --output tmp/theme-settled.json
```

## Verification and limits

- Startup follow-up, 2026-10-31: the newest matching fault/application logs and
  timestamped startup report identified a runtime `NameError` in
  `ModalWindowThemeFilter`: `connect_theme` had been placed in a `TYPE_CHECKING`
  block. Its runtime import is corrected. A fresh-process test now executes the
  real entry-point theme/runtime/dialog-filter/splash setup, substituting only
  the world-owning window so no original world opens. The modal-filter module
  joins `ci_fast`, and bootstrap coverage also joins `smoke`. Other migrated
  theme-helper imports were audited for the same mistake. The startup/theme batch
  passes all 27 tests; repository Ruff and mypy also pass after this correction.
- Fresh-process `ci_fast`: 2,937 passed, 3 skipped, 4,518 deselected. Log/JUnit:
  `tmp/krt120-ci-fast.log` and `tmp/krt120-ci-fast.xml`.
- Repository Ruff, mypy (575 source files), visual policy, complexity policy and
  Help inspection policy pass. No policy ceiling was increased or bypassed.
- Focused current-runtime checks cover rapid selections, replaced/destroyed
  scopes, OK hiding, item-model ownership, hidden reactivation, shorthand local
  styles, six palettes and real browser frame acknowledgement.
- Final focused batch after the narrow lifecycle/shorthand additions: 197 passed;
  `tmp/krt120-focused-final.log` and `tmp/krt120-focused-final.xml`. This includes
  actual 10/15/20 pt action fonts, complete labels across all themes and newly
  shown native tooltip colors. The earlier full `ci_fast` pass predates those
  final narrow additions; it has not been represented as a second full run.
- Rich/source Entity/Event regressions run with legacy and scoped delivery:
  exact authored text, document identity, selection, focus, dirty state and
  undo/redo steps are preserved. Timeline playhead and Longform scroll/selection
  checks also run with both modes.
- Isolated offscreen panel/state matrix: 408 captures under
  `tmp/krt120-scoped-renders`. Workspace comparison: 120 captures each under
  `tmp/krt120-workspace-scoped` and `tmp/krt120-workspace-legacy`.
- Native Windows Qt workspace: 120 captures under
  `tmp/krt120-native-workspace-1.5`, at DPR 1.5 and 1280/760 logical widths.
  Representative normal/narrow/native images were inspected; this is not review
  of every image, an OS scaling change or per-monitor transition acceptance.
- Manifests distinguish requested application font (10/15 pt) from effective
  root font. Global 10 pt QSS means that application-font requests alone do not
  prove enlarged text. Those images are not blanket font-scaling acceptance;
  dedicated action checks verify actual font size and complete labels.
- Automated native screenshots and Qt timings do not establish interactive
  flicker, focus transitions, perceived responsiveness or owner acceptance.
  Native/human checks remain pending. Full regression, package and release gates
  were not run for this uncommitted implementation batch.

The local commit includes the implementation and this evidence. Pushes, version
bumps, releases and issue completion remain separately authorized steps.
