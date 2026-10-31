# KRT-120 historical bounded-pass evidence

This record is superseded by [the visible-first implementation record](README.md).
The measurements below are provisional diagnostics for the earlier bounded pass.

> **2026-10-31 correction:** the original standalone probes below used
> `setDefaultFormat(IniFormat)` plus two-argument QSettings constructors. A fresh
> Windows check proved those constructors still selected NativeFormat/registry
> storage. The old raw samples are retained as historical diagnostics, but their
> temporary-settings isolation claim is withdrawn and they are provisional for
> acceptance. The Apply probe may have changed the local default-theme preference;
> no world/database was opened. No previous preference value has been guessed or
> restored. Further probes use an explicit-INI constructor shim installed before
> project imports, reject unsupported overloads and disable credential access.

Reference record, 2026-10-31. Implementation is uncommitted, based on
`485706ecef32bd9879223b271c8696bc4a706b46`. Linear KRT-120 remains In Progress.
This work preserves the global stylesheet architecture and shipped palettes.

## Change and compatibility boundaries

- Inspector focus rules apply to inputs rather than being copied into buttons.
  Disclosure controls own their theme refresh; constant tab spacing is installed
  once. Touched local stylesheet setters avoid identical assignments.
- Shared button geometry notifications coalesce through a child-owned single-shot
  timer. Size hints remain synchronous, including enlarged and wrapping labels.
- SVG loading has a GUI-thread-owned 256-entry LRU keyed by resolved path/color.
  Successful icons are copied on return; missing/failed assets are not cached.
- Graph themes recolor existing renderer objects without updating the Vis DataSet
  or restarting physics. Page-generation checks and actual JavaScript readiness
  guard latest-theme delivery, replacement, hidden views, empty pages and shutdown.
  Ordinary incremental graph updates also receive the current label color.
- Longform retains the rendered body until the ordinary content/calendar load
  path replaces it. Theme switches rewrap current CSS and install HTML, retaining
  selection and scroll after document layout. HTML installation is still required.
  Authoring documents retain their existing layout/highlighter refresh behavior.

Contracts 2/4/5/6/7/8/9/11 apply: visible routes, keyboard ownership, drafts,
selection/caret, scroll, playhead and undo/redo remain authoritative. Presentation
uses the existing action, supporting, selection and focus roles through shared
StyleHelper methods. There are no new theme roles or interaction exceptions.
Three exact legacy fallback-color exceptions were removed from the visual-policy
baseline after their expressions were replaced by theme-owned lookups; no new
exception or baseline regeneration was used. No reviewed C901 hotspot was touched.

## Performance protocol and acceptance

Run from the repository root with its configured Python:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:QTWEBENGINE_CHROMIUM_FLAGS = "--disable-gpu"
.venv/Scripts/python.exe -m scripts.benchmark_theme_switch `
  --baseline-ref 485706ecef32bd9879223b271c8696bc4a706b46 `
  --output tmp/krt120-benchmark-final.json
```

The benchmark interleaves baseline/current runs, using three fresh processes per
variant/scenario, two warm-up switches and ten measured alternating Dark/Light
switches. Settings are redirected to temporary INI stores. No world or database
is opened. Baseline production modules are loaded from the specified Git revision
through a temporary source overlay; the benchmark fixture and settling logic are
identical for both variants.

Both scenarios use hydrated Entity/Event inspectors and Settings Center at fixed
960 x 720 logical allocations with explicitly registered Segoe UI. The loaded
fixture adds 100 timeline events, a 60-node/59-edge graph, and 40 Longform chapters;
it hides the previously displayed Entity inspector and Settings Center. This is a
generated widget fixture, not a measurement of every application coordinator,
world size, workspace, package or startup path.

Synchronous duration ends when `set_theme` returns. Settled duration also drains
queued geometry/layout/paint work until visible Qt geometry is stable for three
passes, waits for the current graph page and latest-theme acknowledgement, and
waits for two browser animation frames. Native Qt pointer identities are used
because Python wrappers for internal widgets may be recreated between snapshots.
Raw timings have neither a profiler nor the operation-count event filter enabled.
A separate instrumented switch counts stylesheets, geometry notifications, SVG
renders, HTML/page loads, Markdown conversion and Qt style/layout/paint events.
P95 uses nearest-rank selection from all 30 samples in each variant/scenario.

The gate is at least 30% lower editor/settings median settled latency and at most
10% p95 regression in either scenario; 50% improvement is a stretch target.
Earlier unhydrated/missing-font timings, contended diagnostic runs and short
probes are excluded from acceptance.

### Final matched result

The raw 120 samples and separate operation counters are retained in
[benchmark.json](benchmark.json). Python 3.13.14 / PySide6 6.10.1, Windows,
offscreen Qt; no tests or render matrix ran alongside these measurements.

| Scenario | Baseline median settled | Current median settled | Reduction | Baseline p95 | Current p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Editors/settings | 2.384 s | 2.066 s | 13.33% | 2.453 s | 2.173 s |
| Loaded fixture | 3.516 s | 2.713 s | 22.84% | 3.966 s | 2.920 s |

Synchronous medians were 2.128 -> 1.806 s for editors/settings and
2.918 -> 2.396 s for the loaded fixture. P95 settled latency improved by 11.41%
and 26.37%, respectively, so neither scenario regressed at p95.

**The 30% editor/settings acceptance target was not met.** The bounded pass is
implemented and verified, but this is not acceptance of the requested speed
target. No broader stylesheet redesign was attempted. Earlier 30-50% estimates
were optimistic; global application stylesheet repolishing remains the principal
diagnosed cost and this pass deliberately retains that architecture.

Separate instrumented-switch counts from the first process of each variant:

| Operation | Editors baseline/current | Loaded baseline/current |
| --- | ---: | ---: |
| Stylesheet assignments, including application | 598 / 382 | 608 / 391 |
| Geometry notifications | 14,631 / 4,930 | 14,887 / 4,952 |
| SVG renders | 72 / 0 | 77 / 0 |
| Graph page loads | 0 / 0 | 1 / 0 |
| Longform Markdown conversions | 0 / 0 | 40 / 0 |

These counters come from an additional instrumented switch, not the timed
samples. Other processes had the same stylesheet/SVG/page/Markdown counts;
geometry notification counts varied slightly and remain in the raw evidence.
Qt layout/paint/style events and total HTML installations are also in
the raw evidence. Longform still installs HTML; queued geometry work is included
in settled time rather than being hidden after the synchronous measurement.

## Verification and presentation evidence

- 113 focused regressions passed across editor presentation, complete action
  labels, graph themes/incremental updates/lifecycle, Longform themes/calendar
  dates/demand loading, icon cache bounds/copies/retries and geometry coalescing.
- Real Chromium runs in a separate regression subprocess. It verifies rapid
  successive themes, renderer positions, camera, selected node, physics, lexicon
  colors, hidden-view reactivation and empty-state recoloring. Mocked lifecycle
  checks reject callbacks from replaced pages and shutdown.
- Six-theme Rich/Source Entity/Event checks retain document identity, exact
  authored text, selection, focus, dirty state and undo/redo step counts. Timeline
  playhead and Longform selection/scroll checks also pass.
- Focused production action-label gate: 36 records, zero failures, covering
  Entity/Event and overflow controls with normal/enlarged text.
- Repository Ruff, mypy (572 source files), visual policy and complexity policy
  passed. The full regression/release/package suites were not run for this
  uncommitted bounded change.
- Corrected offscreen matrix: 408 captures across all six themes, 960/360 logical
  widths, 10/15-point application fonts, normal/focus/hover/disabled states and
  checked editor disclosures. Timeline, graph and Longform have normal captures.
  Requested/actual widths and DPR are retained in the manifest. Representative
  native and narrow offscreen images were inspected for readable text and routes;
  this is not a claim that every image received independent human review.

Local artifacts retained under the repository's ignored `tmp/` directory:

| Artifact | Purpose |
| --- | --- |
| `krt120-benchmark-final.json` | Final paired raw samples; also retained beside this report |
| `krt120-renders-final/manifest.json` | Corrected offscreen matrix and PNGs |
| `krt120-action-labels/scale-1.0/report.json` | Production action-label checks |
| `krt120-native-1/review.json` | Automated Windows/DPR 1.0 samples and PNGs |
| `krt120-native-1.5/review.json` | Automated Windows/DPR 1.5 samples and PNGs |

The earlier `krt120-renders/` batch shows empty inspectors and missing glyphs and
is explicitly rejected. It is retained only as diagnostic evidence.

## Native and human review limits

A disposable native Qt Windows host used generated Entity data and temporary
settings. Six themes were captured at DPR 1.0 and 1.5, with unchanged OS settings;
the second factor is Qt scaling, not a separate Windows OS/per-monitor review.
Programmatic native screenshots show the production inspector and readable
controls. This one-inspector host is not the performance benchmark fixture.

The Computer Use skill was used to locate and inspect the native host, but its
desktop capture was occluded by another application and provided no useful
accessibility tree. No coordinate input was attempted through the occlusion.
Interactive flicker/responsiveness, actual per-monitor transitions, full native
state coverage and owner/human acceptance remain pending. Automated rendering
and timing do not establish those outcomes or newcomer task-time improvements.

No commits, pushes, version bumps, releases or issue closure are included.
