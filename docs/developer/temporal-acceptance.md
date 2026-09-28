# Temporal uncertainty acceptance

This checklist maps the original temporal uncertainty and graph validity plan
to implementation and regression evidence. A representative lore-day coordinate
is a layout position, not an assertion of an exact historical date.

Test files below are under `tests/unit/`. The graph layout check additionally
uses a rendered QtWebEngine scene: edge-only updates must retain node positions,
camera scale/position, and selection.

| Plan criterion | Implementation and evidence |
| --- | --- |
| 1. Year survives save/reload/export | `test_temporal_precision_roundtrip.py::test_editor_save_reload_export_and_undo`; semantic JSON retains unspecified components. |
| 2. Year end is possible within that year | `core/test_temporal_uncertainty.py::test_shared_succession_validity`. |
| 3. Inactive at next year | Same succession matrix checks the exclusive upper bound. |
| 4. Shared handover has no false overlap | `test_shared_anchor_excludes_false_overlap` and `test_exclusive_roles_distinguish_shared_and_independent_transitions`. |
| 5. Unknown differs from open | `test_unknown_is_not_open`; explicit boundary status is persisted. |
| 6. Possible state effects remain visible | `test_possible_effect_survives_in_state`; Entity Editor lists possible changes and affected fields. |
| 7. Legacy exact dates unchanged | `test_legacy_exact_boundary_stays_exact`; metadata-only edits covered by `test_ordering_only_metadata_does_not_reinterpret_a_legacy_date`. |
| 8. Custom calendar bounds | `test_temporal_authoring.py::test_random_custom_calendar_precision_invariants` covers seeded variable month lengths, leap rules, year variants, zero and negative years. |
| 9. Shared graph/map/state evaluation | `test_graph_modes_share_evaluator`, `test_map_temporal_visibility.py`, and resolver tests consume `resolve_temporal_window`. |
| 10. Indeterminate is not silently false | `test_unknown_anchor_and_bad_calendar_are_indeterminate`; graph reveal/count, resolver diagnostics, and map question-mark cues retain unknown timing. |
| 11. Soft padding is not evidence | `test_qualifications_supply_no_invented_evidence`; explicit limits tested separately. |
| 12. Claims stay separate | `test_preferred_source_survives_editor_save_reload_export_and_undo` and `test_claim_removal_preserves_identity_and_explicit_bounds`. |
| 13. Reopened year is not January 1 | Precision round-trip tests inspect reopened date text. |
| 14. Year entry needs no advanced controls | Text-first `CompactDateWidget`; worker/editor/save path in `test_calendar_context_service.py`. |
| 15. Semantic source-event relation end | Relation editor source-event binding and named-event choices retain identity without copying an exact date. |
| 16. Inspector explains ambiguity | Entity Editor uses possible-change prose rather than resolver enum names. |
| 17. Graph uncertainty discoverable | `test_graph_hidden_uncertainty_can_be_revealed_and_selected`. |
| 18. Coarse precision is informational | Default date feedback accepts partial dates; `test_conflicting_sources_are_distinct_from_coarse_precision`. |
| 19. Conflict differs from imprecision | Disjoint source evidence displays “Conflicting source dates”; ordinary precision does not. Same conflict test and preferred-source editor test. |
| 20. No automatic legacy reinterpretation | Compatibility reader retains numeric exactness; no automatic migration is run. |
| 21. Non-color uncertainty cues | Graph dashed edges/count/tooltips, map `(?)` labels, trajectory tooltip, and timeline dotted/hatched bounds; `test_map_widget.py::test_uncertain_owner_trajectory_has_non_color_cue` and `test_temporal_display.py`. |
| 22. Inactive current edges hidden | `test_graph_filters_time_before_deriving_connected_nodes` and graph mode matrix. |
| 23. Year-bound edge remains possible | `test_graph_modes_share_evaluator`, graph presentation consumes its status unchanged. |
| 24. Hidden uncertainty counted/revealable | Reveal test covers both explicit reveal and selected-node adjacency. |
| 25. No independent widget/projection evaluator | Graph service evaluates snapshots; `test_graph_projection_preserves_status` covers projection. |
| 26. Edge updates preserve graph view | Graph builder incremental update freezes positions when node IDs are unchanged; rendered QtWebEngine verification checks positions, pan, zoom and selected node. |
| 27. Distinct modes do not mutate records | Graph mode matrix and `test_graph_filters_time_before_deriving_connected_nodes` compare persisted relations before/after queries. |

## Additional plan safeguards

- `test_chronology_validation.py`: global cycles, shared transitions, strict
  order in coarse periods, and multi-edge date feasibility.
- `test_chronology_service.py`: incoming projection, undo, date-save guard,
  and legacy rule editing.
- `test_event_chronology_dialog.py`: incoming order and unavailable target UI.
- `test_relative_anchor_bounds_keep_only_evidence_and_no_false_identity`:
  before/after/offset references retain only known bounds, without inventing
  a shared transition between independently constrained dates.
- `test_anchor_deletion_requires_dependency_confirmation_and_undo`:
  dependency preflight, confirmed deletion, unchanged dependent assertions, undo.
- `test_limits_do_not_invent_duration_or_nominal_containment`: explicit hard
  limits remain separate from nominal approximation and event duration.
- Precision drag and explicit range-meaning tests cover editor/command/undo.
- `test_temporal_display.py` covers year-only occurrence, uncertain starts with
  known durations, separate end assertions, open soft dates, and lane spacing.

## Deliberately optional scope

The plan marks the legacy precision review assistant and EDTF export as optional.
Neither is implemented. Existing exact dates are preserved and JSON exports
retain all semantic data. Derived database indexes require profiling evidence;
none are added speculatively. Trajectory visibility uses owner validity;
uncertain keyframe interpolation is not part of the original plan.
