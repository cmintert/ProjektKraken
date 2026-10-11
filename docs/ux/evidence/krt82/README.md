# KRT-82 — Action label integrity evidence

KRT-82 implements [Contract 11](../../authoring-contract.md), alongside Contracts
2/5/6/7/8 and the [visual vocabulary](../../visual-interaction-vocabulary.md).
The implementation is on branch `button_gate`. The issue remains open and native
Windows screenshot approval is **pending**; beta/release sign-off remains blocked.

## Evidence boundary

Production widgets are rendered with application QSS, isolated settings and
synthetic snapshots. The workspace fixture uses the production shell, application
menus and inspectors, with inert stand-ins for the other independently audited
panels. It does not launch the database worker, save worlds or call AI providers.

| Axis | Required coverage |
| --- | --- |
| Application client area | 1280 × 720 and 1600 × 900 Qt logical pixels |
| Inspectors | 240, 360 and 800 px allocations; actual sizes are recorded |
| Simulated Qt scale | 100%, 125%, 150%, 200% in separate processes |
| Independent text enlargement | 100%, 125%, 150%, 200% |
| Themes | Every shipped theme from `themes.json` |
| Wording | Production text and deterministic longer action labels |
| Presentation | Default, disabled, tab/settings destinations and disclosures |
| Native review | Every audited surface at every required Windows OS scale |

Longer labels double vowels and add brackets. For example, the test fixture uses
`[Mooree aactiioons]` for **More actions**. This is pseudo-localization for layout
stress, not production wording or a translation. Signals and action objects remain
unchanged. Geometry checks do not establish human readability, native DPI behavior
or screen-reader conformance.

Source inventory records actionable construction sites and explicit fixture
ownership. Registration is not a claim that every data-dependent/contextual mode
has been reviewed. Native review must include populated lists, map editing and
layer modes, relationship drafts, focus writing, split panes, menu destinations,
provider states and unfinished authoring state. Missing review remains pending.

## Implementation and review

Shared controls measure font/style content rectangles, reflow groups, retain full
multiline wording, and provide labeled secondary overflow. Save actions retain
their original controls and direct routes. Native dialog button boxes preserve
roles/defaults while stacking. Dense formatting and Sheet commands retain their
original actions in visible menus. Header/configuration scrolling reserves enough
space for action labels without increasing application/dialog minimum dimensions.

Tests deliberately exercise undersized buttons, height/ancestor clipping,
collisions, changed menu wording, unknown adapters and missing source owners.
Wrapping controls retain keyboard activation and a full label click target;
overflow retains availability/check states and transfers focus to its visible
route when a focused secondary control moves there.

The touched relation-type choice preparation was extracted from
`RelationForm.__init__`: reviewed complexity decreases **17 → 16**, with the same
allowance ID and a reduced ceiling. Exact legacy color exceptions were retired
for the UnifiedList color label, backup path, color-picker initial swatch and
raster preview. Scroll-area viewports and content use `app_bg` in every theme.
The Qt theme adapter also maps native panel/viewport palette roles to existing
theme tokens, preventing Windows' light fallback during live theme switches.
Global menu/list selections use `selection_bg`/`selection_text`, and pressed
buttons use their semantic action roles. The three obsolete production-QSS
foreground exceptions were retired. Other baseline exceptions were retained.

## Reproduction and release review

```powershell
.venv\Scripts\python.exe -m scripts.check_action_labels --matrix fast --report-dir tmp/action-labels-fast
.venv\Scripts\python.exe -m scripts.check_action_labels --matrix full --report-dir tmp/action-labels-full
```

Reports record revision, presentation fingerprint, environment, fonts,
requested/actual logical dimensions, device pixel ratio, physical images,
surface/state, full wording and required/available geometry. Native menus are
opened before measurement and capture. Streaming records and current-fixture
progress survive an interrupted renderer; process failure cannot count as a pass.

[Native review manifest](native-review.json) is intentionally pending. Release
preflight requires an approved, current manifest with hashed, decodable native
captures and records at all four OS scales. Follow the
[release reviewer checklist](../../../developer/action-label-release-gate.md).
Automated captures cannot populate native approval. Commit, push and release are
separately authorized delivery steps.

## Baseline automated results — 2026-10-11

At baseline commit `bbc104e3`, the complete simulated matrix passed
**95,808 cases with zero failures**:
23,952 at each of the four Qt scale factors, covering 82 registered production
surfaces, six themes, four text factors and both wording sets. Every source
inventory entry has a registered fixture. Registration does not replace the
remaining contextual-mode/native review described above.

- `ci_fast`: **1,889 passed, 2 skipped**, 4,440 deselected.
- `smoke`: **19 passed**, 6,312 deselected.
- Ruff, repository-wide mypy (462 files), visual policy, complexity policy,
  test policy, dependency/schema checks and strict documentation build: passed.
- Qt theme/background and label regressions: passed across all six themes.

The suites emit the existing Starlette `httpx` deprecation warning. No Windows
package build or native screenshot approval is represented by these results.
[Verification record](verification.json) lists the completed gates. A successful
render with `--require-native-review` was also rejected as expected because the
native approval manifest is pending.

[Coverage manifest](coverage-manifest.json) records configuration counts,
surface/state and requested/actual dimensions, source/environment hashes,
representative captures and reviewer status. The four `matrix-scale-*.json.gz`
archives retain every measured record while deduplicating identical control
snapshots. To restore a record's original control list after JSON decompression:

```python
record["controls"] = archive["control_sets"][record.pop("control_set")]
```

The archive's `report` member contains the original environment/inventory header.
Every restored record was compared with its original scratch record. Retained
archives total approximately 12 MB; 21 representative before/after captures
include narrow inspectors, the minimum client area, reflow and all theme palettes.
Other captures remain at the source-run paths recorded in the manifest.

Retained reports: [100%](matrix-scale-1.0.json.gz),
[125%](matrix-scale-1.25.json.gz), [150%](matrix-scale-1.5.json.gz),
[200%](matrix-scale-2.0.json.gz).

| Surface | Before | After |
| --- | --- | --- |
| Graph filter, 360 px | [Clipped type selector](before-scale1.0-GraphFilterBar-360-default-dark_mode-text1.0-long0.png) | [Reflowed controls](after-scale1.0-GraphFilterBar-360-default-dark_mode-text1.0-long0.png) |
| Generation controls, 200% text | [Checkbox/prompt collision](before-scale1.0-LLMGenerationWidget-360-default-dark_mode-text2.0-long0.png) | [Scrollable complete longer labels](after-scale1.0-LLMGenerationWidget-360-default-dark_mode-text2.0-long1.png) |
| Analysis dark theme | Native light-background fallback was reproduced during diagnosis | [Theme-owned background](after-scale1.0-MainAnalysisPanel-360-default-dark_mode-text1.0-long0.png) |
| Minimum workspace, 200% Qt/text | Earlier clipped Save wording was reproduced during diagnosis | [1280 × 720 logical client](after-scale2.0-WorkspaceShell-1280-default-dark_mode-text2.0-long1.png) |

[Format equivalence](format-equivalence.json) records the required final commit
formatting: all 26 affected Python syntax trees remain identical. The matrix
identifies its pre-format input fingerprint; the proof also records the formatted
fingerprint. Formatting did not alter the verified presentation behavior.
Temporary diagnostic runs remain under `tmp/krt82-*`; fontless early diagnostics
are not acceptance evidence.

## Compact layout and workstation resource follow-up

The user-reported native screenshot exposed excessive vertical allocation.
At 800 × 1100 logical pixels, Event header/footer allocations were 280/280 px
for 65/34 px of content. They now use 65/34 px; inspector body height grows
from 500 to 961 px. At 480 × 1100, the populated Explorer filter group drops
from 464 to 34 px and its list grows from 463 to 895 px. Overflow uses remaining
row width rather than compressing **More actions** into a column of letters.

The default audit is now `quick`: 44 representative records, one renderer,
normal/enlarged text and no passing screenshots. Its initial measured run
passed in 16.4 seconds. Per-surface quick checks are smaller still. Reports stream
to disk, overlapping audits are rejected, and Windows children run at
below-normal priority. `fast` and explicit `full` release coverage are retained.

The retained exhaustive reports above describe the baseline commit; they are
not a new complete matrix for this follow-up. Broad `ci_fast` and exhaustive
rendering are intentionally not repeated while the user is working. Focused
allocation, label and resource-guard regressions verify this batch; native
review and release verification remain pending.

[Follow-up verification](compact-followup-verification.json) records the bounded
checks. Offscreen allocation captures:

| Surface | Before | After |
| --- | --- | --- |
| Event inspector | [Wasted header/footer height](compact-followup/before-EventEditorWidget.png) | [Content-sized rows](compact-followup/after-EventEditorWidget.png) |
| Entity inspector | [Wasted header/footer height](compact-followup/before-EntityEditorWidget.png) | [Content-sized rows](compact-followup/after-EntityEditorWidget.png) |
| Populated Explorer | [Tall filter group](compact-followup/before-UnifiedListWidget.png) | [Compact filters and larger list](compact-followup/after-UnifiedListWidget.png) |
