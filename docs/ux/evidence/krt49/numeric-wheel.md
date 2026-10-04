# Numeric wheel navigation — KRT-49

Verified 2026-10-04 with Python 3.13.14, PySide6/Qt 6.10.1, Windows,
Qt offscreen platform. These are automated runtime checks, not a new human
benchmark run or a claim of measured creator improvement.

## Reproduction and policy

The production `RelationEditDialog` uses a scrollable form. Before the fix,
delivering a negative wheel step to its unfocused confidence input while notes
owned focus changed confidence from 0.7 to 0.6. No rounding change is involved;
the separate relation-row decimal presentation issue stays with KRT-22.

Shared `ScrollSafeSpinBox` and `ScrollSafeDoubleSpinBox` use StrongFocus and
ignore wheel events when unfocused. Qt propagates these events to surrounding
scroll content. A click or Tab explicitly focuses a numeric field, allowing its
normal wheel behavior. Typing, Up/Down keys and visible step arrows remain
available; the color scrubber also retains horizontal dragging. Leaving the
numeric field ends wheel editing. No global event router is installed.

Contract 2 governs intentional input; 5 protects notes focus and authored values;
8 supplies the same policy across equivalent controls; 9 protects save and
undo semantics. Existing labeled fields and arrows remain the visible routes.
Keyboard input belongs to the focused field. No contract rule is revised and
no new exception is introduced.

## Inventory and scope

All direct integer/decimal spin-box imports in production GUI code now use the
shared controls, across 25 existing modules:

| Family | Surfaces |
| --- | --- |
| Relations and authored attributes | Relation weight/confidence/boundary offsets; numeric attribute delegate |
| Dates and durations | Compact date/year/hour/minute; compact duration; lore date and duration; chronology gap; analysis date limits |
| Map and icons | Layer opacity/zoom/raster values and gradient/alpha controls; raster queries/defaults; palette color scrubbers; calibration/scale/marker size/border; icon diameter and anchors |
| Settings and generation | AI settings; AI search result count; LLM generation; backup interval/retention; calendar preview; lexicon styling |

`NumericScrubberSpinBox` inherits the shared integer control. Qt stylesheet
selectors remain `QSpinBox`/`QDoubleSpinBox`, preserving native theme matching.
Combo boxes, sliders and canvas zoom gestures are outside this numeric-input
scope. Sheet-builder column weight uses Qt's single-field `QInputDialog.getInt`;
its initially focused numeric input remains Qt-owned and is not a scrollable
multi-field form. This inventory does not claim every possible numeric UI is
affected by the original confidence defect.

## Verification

`tests/unit/test_numeric_wheel.py` delivers wheel input through `QTest.wheelEvent`
to the real QWindow, including Qt hit testing and parent propagation:

- Production relation forms at widths 400 and 800 px, height 450 px; wheel over
  both spin-box and line-edit hit areas; angle steps and pixel-plus-angle input.
  The scroll bar moves, confidence emits no value change, `get_data()` remains
  identical, and notes keep focus.
- Integer, decimal and color scrubber inputs: unfocused wheel leaves values
  alone; Tab and click focus enable wheel editing; Up and typed entry still work.
- Native visible step arrows remain usable for integer and decimal inputs.
- A revised relation note saves without altering confidence, weight, custom
  attributes, dynamic event binding or payload; undo restores original metadata
  and redo restores the deliberate note change, using real command/database code.

The new module has 14 passing cases and explicit `ci_fast` membership. The
focused relation/date/duration group passed 73 cases before the additional
save/undo/redo case, which then passed in the final 14-case wheel module.
The bounded fast suite passed 1,288 cases with 2 skips before that extra case.
Full-source mypy passed for 426 modules. The collection baseline includes the
14 new cases. No executable build or new participant video was performed.
