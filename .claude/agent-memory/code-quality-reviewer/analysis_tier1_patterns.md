---
name: Tier 1 Analysis Feature Patterns
description: Patterns and recurring issues from TemporalAnalyzer, WorldValidator, AnalysisPanel, and related Tier 1 code
type: project
---

## TemporalAnalyzer (src/services/temporal_analyzer.py)

Overall quality is high. Docstrings are complete, type hints are present throughout,
the class is focused (single responsibility), and private method decomposition is clean.
Issues are medium/low severity only.

**Recurring O(n*m) pattern in _analyze_character_lifespans:**
Iterates all relations for every entity (O(entities * relations)), then iterates all
events for every entity again (O(entities * events)). Pre-bucket relations into a
dict[entity_id, list[rel]] in O(relations) before the entity loop to fix the first.

**db_service typed as Any:**
__init__ accepts db_service: Any. The correct structural type is DatabaseService from
src.services.db_service. Use TYPE_CHECKING import to avoid circular dependency. Flag
whenever Any is used for a known concrete service type in this codebase.

**Variable name inconsistency life_span vs life_span_years:**
Local var named life_span is assigned then passed as life_span_years=life_span.
Rename the local to life_span_years to match the dataclass field.

**Misleading variable name dated_lore_dates in analyze():**
All events always have lore_date (not optional); the "dated_" prefix is meaningless.
Rename to lore_dates.

**_GAP_THRESHOLD comment redundancy:**
Module docstring and inline comment on _GAP_THRESHOLD both describe the same thing.
The constant name is self-documenting; remove the inline comment.

## Test file (tests/unit/test_temporal_analyzer.py)

**Helper factories make_event and make_entity lack docstrings.**
Both are module-level public helpers used across four test classes; each needs a one-liner.

**Repeated entity+relation boilerplate in TestDetectTemporalConflicts:**
Each of the 6 tests in that class creates and inserts e1+e2 entities individually.
A class-level fixture or make_relation_pair() helper would eliminate the 5-line repetition.

**next() without default sentinel in TestAnalyzeCharacterLifespans:**
Used in 9 tests as next(ls for ls in ... if ls.entity_id == "e1") with no default.
If entity is absent, StopIteration surfaces as a confusing error. Prefer
next(..., None) + assert lifespan is not None.

**Test marker mismatch:**
All four test classes are @pytest.mark.unit but every test hits a real db_service
fixture — they are integration tests in practice. Same pattern seen in test_world_validator.py.

## WorldValidator patterns (from prior review, src/services/world_validator.py)

- _check_orphaned_entities and _check_completeness_scores both do O(entities * relations)
  inline relation counting — extract _build_relation_count_map helper.
- Magic numbers 20 (min description length) and 2 (min tag usage) — define named constants.
- from typing import Any alongside Python 3.13 syntax — flag when Any can be narrowed.

## AnalyzeTemporalCommand (src/commands/analysis_commands.py, reviewed 2026-04-13)

- execute() and undo() use string-quoted "DatabaseService" even though DatabaseService is
  already imported under TYPE_CHECKING — should use the unquoted name, exactly as
  ValidateWorldCommand does in the same file. This is a consistency issue.
- The structural duplication between ValidateWorldCommand and AnalyzeTemporalCommand is
  acknowledged and intentional; the pattern is correct for read-only analysis commands.
  Do not flag it as a true duplication defect — note it as acceptable structural symmetry.
- from_dict() accepts `data: dict` but never reads from it (no fields to restore). The
  parameter exists only to satisfy the BaseCommand interface. This is correct as-is.

## TemporalPanel (src/gui/widgets/temporal_panel.py, reviewed 2026-04-13)

- Three QTableWidget setup blocks in _init_ui() are structurally identical (6 lines each):
  setEditTriggers, setSelectionBehavior, setStretchLastSection, setSizePolicy, addWidget.
  Extract a _make_table(headers) helper that returns a configured QTableWidget.
- _populate_gaps_table uses f"{gap.start_date:.0f}" and f"{gap.end_date:.0f}" format
  strings. These are float-format specifiers on what may be date objects — verify the
  type of start_date/end_date in TimelineGap. If they are not floats/ints this will
  raise TypeError at runtime.
- _init_ui() has no docstring (private method, acceptable, but worth noting the pattern).
- Section labels (gaps_label, conflicts_label, lifespans_label) are local variables
  with no self reference — they cannot be styled or updated later. Acceptable for a
  read-only display panel, but worth noting.

## IntelligenceAnalyzer (src/services/intelligence_analyzer.py, reviewed 2026-04-13)

Overall quality is high. Docstrings are complete, type hints are present, and sub-analyzer
decomposition is clean. Issues are low severity only.

**Import ordering violation (stdlib vs local):** `import logging` appears at line 27, after the
local `src.*` imports at lines 18-25. Must be moved to the stdlib block (before src imports),
or at minimum before any local import. Isort / ruff-I will flag this.

**`Optional[Provider]` instead of `Provider | None`:** Line 70 uses `Optional[Provider]` (imported
from typing). With `from __future__ import annotations` active and Python 3.13 target, use
`Provider | None` directly. Same applies to the `Optional` in the import list; it can be dropped.

**Audit log entry shape duplication across three sub-analyzers:** Each of `_detect_plot_holes`,
`_infer_relations`, and `_generate_lore` builds near-identical success and error audit dicts inline
(5-6 key/value pairs each, duplicated for success and error cases). A small `_make_audit_entry`
helper would eliminate this across all three loops.

**`_FakeProvider.__init__` has no docstring** (test file, line 42). `generate` and `metadata`
have one-liners; `__init__` does not. The constructor has non-obvious parameters (`raise_on_call`
semantics). Add a one-liner.

**`_make_entity` line length violation (test file, line 81):** The `Entity(...)` constructor
call is well over 88 characters on a single line. Split into multi-line form.

**Test marker mismatch (recurring pattern):** All four test classes use `@pytest.mark.unit`
but each test hits the real `db_service` fixture. Same pattern as `test_world_validator.py`
and `test_temporal_analyzer.py` — functionally integration tests.

**`idx` variable is unused in `_parse_plot_holes`:** `for idx, part in enumerate(parts[1:])` —
`idx` is only used in the `issue_id` f-string. This is intentional and correct; not a bug.

## analyze_temporal slot (src/services/worker.py, reviewed 2026-04-13)

- Structural duplication with validate_world slot is intentional and correct.
  Both slots follow the same emit-try-finally pattern; the differences (command class,
  signal name, status strings) make extraction into a shared helper impractical without
  significant complexity.
- f-string in logger.error call uses lazy formatting instead of %s — minor style issue.
  Consistent with validate_world slot (same pattern there), so not a new regression.

## RunIntelligenceAnalysisCommand (src/commands/analysis_commands.py, reviewed 2026-04-13)

- Structurally identical to ValidateWorldCommand and AnalyzeTemporalCommand — this is
  intentional and correct per the read-only analysis command pattern. No defect.
- `from_dict` return type uses quoted string literal ("RunIntelligenceAnalysisCommand")
  on line 245. All three commands in the file do this consistently. With
  `from __future__ import annotations` already present (line 7), the quotes are redundant
  but not incorrect. Acceptable; consistent with sibling commands.
- `analysis_type` parameter validated only by the IntelligenceAnalyzer downstream — no
  guard in the command itself. This is fine for the current design.
- Class docstring has an Args: section describing __init__ parameters, which is unusual
  (args belong on __init__'s own docstring, not the class docstring). Both docstrings
  exist — this creates minor redundancy. Consider removing Args: from the class docstring
  and relying solely on __init__'s Args:.

## MainAnalysisPanel (src/gui/widgets/main_analysis_panel.py, reviewed 2026-04-13)

Overall quality is high. `from __future__ import annotations` is present, Dumb UI
principle is correctly observed, slots use `@Slot(object)`, logger uses `%s`-free
plain string literals (not f-strings) in debug calls. No coordinator reference inside
the widget. Issues are low severity.

**`logger` is used** — three `logger.debug(...)` calls with plain string literals (not
f-strings), which is correct style. No dead-logger issue here (unlike TemporalPanel and
IntelligencePanel).

**`setLayout` redundant after `QVBoxLayout(self)`:** `_init_ui()` calls both
`QVBoxLayout(self)` (which sets the layout) and `self.setLayout(layout)` at the end.
The second call is a no-op. Safe to remove `self.setLayout(layout)`.

**Tab indices are magic numbers:** `setCurrentIndex(0)`, `setCurrentIndex(1)`,
`setCurrentIndex(2)` in the three slots. Define `_TAB_VALIDATION = 0`,
`_TAB_TIMELINE = 1`, `_TAB_INTELLIGENCE = 2` as class-level constants.

## ConnectionManager.connect_analysis_panel (src/app/connection_manager.py, reviewed 2026-04-13)

**Lambda for `intelligence_btn` is acceptable but has a subtle issue:**
`lambda: coord.run_intelligence_analysis()` captures `coord` from the enclosing
scope. This is fine because `coord` is a local variable bound before the lambda is
created and is not expected to be reassigned. The lambda exists because
`run_intelligence_analysis` has a default argument (`analysis_type="all"`) and
QPushButton.clicked emits a `checked: bool` argument — connecting directly without
the lambda would pass `False`/`True` as `analysis_type`, corrupting the call.
The lambda is the correct approach here. It could alternatively be an explicit
`lambda _checked: coord.run_intelligence_analysis()` to document that the bool
argument is intentionally discarded, which is marginally clearer.

**`connect_analysis_panel` docstring is accurate** — it correctly states that it wires
worker report signals (queued, cross-thread) and trigger buttons to the coordinator.
No issues.

**`from __future__ import annotations` missing in connection_manager.py** — same gap
as main_window.py. Both files use `from typing import Tuple, Union, Optional` (legacy
forms). With `from __future__ import annotations` present, `ConnectionSpec` could be
defined using `|` union syntax and built-in tuple/callable directly.

**`Tuple`, `Union`, `Callable` from typing in connection_manager.py (line 11):**
Python 3.13 target + `from __future__ import annotations` would allow
`tuple[object, str, Callable, str]` and `... | ...` unions. The `Callable` import
from `typing` is still needed (no built-in replacement). But `Tuple` → `tuple` and
`Union` → `|` are available.

## UIManager setup_docks Analysis block (src/app/ui_manager.py, reviewed 2026-04-13)

The new Analysis Suite dock block (lines 354-370) is structurally identical to the
History dock block above it — same addDockWidget area, same tabifyDockWidget target.
This is intentional and mirrors the established pattern; not a defect.

**`from typing import Any, Dict, Optional` in ui_manager.py (line 7):**
Legacy imports — `Dict` → `dict`, `Optional` → `T | None`, `Any` is acceptable.
`from __future__ import annotations` is absent from this file.

## main_window.py `_init_widgets_skeleton` analysis_panel block (reviewed 2026-04-13)

The deferred `from src.gui.widgets.main_analysis_panel import MainAnalysisPanel`
import follows the same pattern as the History panel deferred import just above it.
Both use inline `from ... import` inside the method body. This is an existing
convention in `_init_widgets_skeleton` for heavier widget imports — not a new violation.

**`from typing import Any, Optional` in main_window.py (line 7):**
Legacy `Optional` — no `from __future__ import annotations` present.
Both main_window.py and ui_manager.py are pre-existing files; these are not new
regressions introduced by the Tier 1 changes.

## IntelligencePanel (src/gui/widgets/intelligence_panel.py, reviewed 2026-04-13)

- Missing `from __future__ import annotations` — same gap as TemporalPanel and
  AnalysisPanel (all three sibling panels have this issue, not just IntelligencePanel).
- `logger` is imported and instantiated (line 21) but never called anywhere in the file.
  Same dead-variable pattern exists in analysis_panel.py. Both should remove the import
  or add appropriate debug logging.
- `_make_table()` is byte-for-byte identical in TemporalPanel and IntelligencePanel (6-line
  helper). AnalysisPanel inlines the same logic instead of using a helper. The duplication
  is acceptable as long as the three panels remain standalone widgets with no shared base.
  If a fourth panel is added, extract a shared `_make_analysis_table()` mixin or utility.
- `_populate_lore_table` uses `f"{filler.start_date:.0f}"` and `f"{filler.end_date:.0f}"`.
  LoreGapFiller.start_date and end_date are declared as `float` in analysis.py, so the
  format specifier is correct.
- f-strings used in `_update_header` for the header label text — these are display strings
  in Qt widgets, not logger calls, so f-strings are appropriate here (not a violation).
- Section labels ("Plot Holes", "Relation Proposals", "Lore Gap Suggestions") are created
  as anonymous QLabel locals, consistent with TemporalPanel pattern. Acceptable for
  read-only display panels.
