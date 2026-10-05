# KRT-45: Supporting-feature refinement

Recorded 2026-10-05 against intermediate implementation
`7f723d08acd05a1a6487823e38be9a2951d79f5f`. The user observed that Timeline,
Summary, Generate description, Map appearances and World context looked like
large unexplained commands and overloaded the cleaner editor. They selected
contextual tools, then two directly visible text actions, and approved this
implementation. KRT-45 remains In Progress pending full human acceptance.

## Current routes and purpose

| Capability | Visible route | Meaning and state |
| --- | --- | --- |
| Summary | Summary… directly below the description | Opens/closes the existing inline panel; “A short version of this description.” Availability is shown beside the action; it does not promise that staged content was saved |
| Description generation | Draft with AI… beside Summary… | Opens/closes the existing generator; “Generate a draft, then review it before applying.” Generation and reviewed application remain explicit existing actions |
| Entity timeline | History & context → Linked events | Existing connected-event document ordered by date; omitted from Event inspectors because they have no corresponding timeline panel |
| Raster associations | History & context → Map layer links | Existing raster layer links, not a claim to list every map marker or placement |
| Known world facts | History & context → World context | Existing read-only renderer, links and bounded More disclosure |
| Independent World context | Inspector More → Open World context below | Same live widget, placeholder, Show/Return here and reset behavior; detached status also appears in the collapsed section caption |

The information heading uses a chevron, subtle separator and wrapping caption:
“Read-only information: linked events, map layer links and known world facts.”
Its subheadings are non-interactive labels, not additional large disclosure
buttons. The two writing actions have transparent default backgrounds and a
visible keyboard-focus treatment. They align with the description field in wide
forms and reflow using their actual available row width.

All supporting panels start closed at construction. Summary and AI panels may
remain open concurrently. Showing or hiding a panel changes visibility only:
it neither starts generation nor commits/cancels an unfinished summary edit.
The description's source caption and dated-description action stay in their
existing ownership workflow.

## Preservation and interfaces

Shared presentation moves the existing Summary and AI action widgets once and
retains their original signal connections. Their containers receive explanatory
captions. Shared composition groups the original timeline, map-link label and
World context renderer. The existing linked-events document now fits its
content, including the empty state; Overview owns its vertical scrolling. Its
event links, data and rendering semantics are unchanged.

There are no database, command-payload, worker or public destination-ID changes.
The internal composition inputs now explicitly supply the existing linked-events
and map-link widgets. `world_context` activation opens History & context when
embedded, or activates its current independent pane when detached. Return/reset
preserve inner presentation choices. Same-object refresh retains the chosen
supporting expansions and existing nested context More state.

Ordinary date, duration and participant disclosures retain their previous
treatment. The supporting heading and writing-action styles are scoped and
refresh through ThemeManager. Contract v1 rules 1, 4, 5, 6, 7, 8 and 9 apply;
keyboard ownership remains Contract 2, and the separate counting requirement
remains Contract 10. No rule was changed.

## Rendered review

The earlier [initial implementation captures](after/captures.json) remain
unchanged. [Refinement manifest](refinement/captures.json) records **228 component
images and 12 More-menu images**: both inspectors, dark/light themes,
331/560/871 px actual widths, 720 px normal height and 480 px short layouts.
Production `main.qss`, Segoe UI 10 pt, Windows 11, Python 3.13.14 and
Qt/PySide6 6.10.1 were used with offscreen Qt and isolated settings. The manifest
records source hashes and the pre-commit base revision.

Synthetic snapshots exercise summary availability, typed fields, read-only
context, omitted-count disclosure and empty-summary controls. These are isolated
component renders with an empty attachment provider, not database persistence
checks or human task results. Added omitted-count data makes bounded More
reachable in both inspectors; it is not measured participant behavior.

Visual review verified the quiet collapsed surface, readable purpose captions,
both writing panels, compact empty history, World context navigation/split homes,
and footer access in short layouts. Every recorded component fits its requested
width, with zero Overview horizontal-scroll range and no visible scroll area
reporting a nonzero horizontal-scroll range.

| Review | Before (`7f723d08`) | Refined |
| --- | --- | --- |
| Collapsed Entity, dark 331 px | [Five supporting rows](after/entity-dark_mode-331-support.png) | [Quiet tools and one heading](refinement/entity-dark_mode-331-support.png) |
| Collapsed Entity, light 871 px | [Supporting rows](after/entity-light_mode-871-support.png) | [Writing-field alignment](refinement/entity-light_mode-871-support.png) |
| Short Event, light 331 px | [Initial short layout](after/event-light_mode-331-short.png) | [Quiet support and persistent footer](refinement/event-light_mode-331-refinement_short.png) |
| Summary purpose | Existing panel retained | [Open Summary, light 871 px](refinement/entity-light_mode-871-summary.png) |
| AI purpose | Existing reviewed-generation path retained | [Open AI drafting, light 331 px](refinement/entity-light_mode-331-ai_draft.png) |
| Concurrent panels | Existing independent disclosures retained as actions | [Both open, dark 331 px](refinement/entity-dark_mode-331-writing_panels.png) |
| Empty summary | Existing explicit Generate action retained | [Empty Summary, dark 560 px](refinement/entity-dark_mode-560-empty_summary.png) |
| Entity information | Separate timeline/map/context bars | [Grouped information, dark 331 px](refinement/entity-dark_mode-331-information.png) |
| Event information | No Entity timeline to fabricate | [Event information, light 331 px](refinement/event-light_mode-331-information.png) |
| Bounded additional context | Existing More remains | [Additional context, dark 560 px](refinement/entity-dark_mode-560-information_more.png) |
| Independent supporting view | Existing World context split | [Split home and return, light 331 px](refinement/entity-light_mode-331-context_split.png) |

Reproduce with offscreen Qt:

```powershell
.venv\Scripts\python.exe -m scripts.capture_inspector_evidence --output tmp/krt45/refinement-review
```

## Verification

| Gate | Result |
| --- | --- |
| Focused inspector/presentation/splitter, Entity/Event, coordinator, focus writing, checkpoint, cursor/autosave, Sheet, Summary, editor mixin, context renderer and unsaved-change tests | **355 passed, 1 skipped, 1 deselected**; 31.95 s |
| Bounded `pytest -m ci_fast -q -o addopts= --maxfail=3` | **1,379 passed, 2 skipped**, 4,373 deselected, 23 subtests passed; 43.24 s |
| Ruff: source, tests and capture script | Passed |
| `mypy src/` | Passed; 430 source files |
| Test policy update and subsequent validation | Passed; 5,754 collected, 1,381 ci_fast; 15 added cases; no removed tests or changed existing membership |

The pre-existing MainWindow test with a mock lacking
`show_world_at_event_requested` remains explicitly deselected, as established
against the immutable original baseline in the [initial report](README.md).
The focused coordinator Save/Discard/Cancel, failure and temporal checkpoint
tests pass. CI retains two skips and an existing Starlette/httpx deprecation
warning; none is counted as a passed test.

New cases exercise initial contextual placement, keyboard opening without
mutation or generation, concurrent unfinished summary edits and generator
inputs, same-object choices, split/reset retention, existing-document history
fitting, prose selection/scroll/undo, theme refresh and explicit Summary
generation/manual-edit signals. These check actual widget state and authoring
signals instead of treating visual rearrangement as semantic success.

## Acceptance and delivery boundary

The preserved original baseline remains `5e7942f7`; `7f723d08` is the intermediate
canonical layout, not a completed human run. The [human comparison register](benchmark-comparison.md)
now points to the final refinement revision for the after run. All twenty tasks
remain unmeasured. Record destination changes, writing-panel openings,
information disclosures, bounded More, wrong turns, ambiguity and assistance
separately, protecting KA-08/10/15/19/20.

Fewer permanent bars is an observed structural/rendering result. It does not
establish improved first-use understanding or fewer unnecessary human actions.
Refine and repeat if the full comparison fails. Keep KRT-45 open until human
acceptance is recorded against the verified commit.

No executable build or push. Unrelated temporary-artifact deletions are preserved
and excluded from the refinement commit.
