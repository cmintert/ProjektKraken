# KRT-26 investigation — 2026-10-08

Issue: https://linear.app/projektkraken/issue/KRT-26/protect-unfinished-map-edit-sessions-from-context-replacement

Source revision: 7b7fc211acb1780ed3fa7177a4d0b2db126f5cb5. Investigation only; no application changes.

## Confirmed source findings

1. TrajectoryEditCoordinator.on_map_selected (src/app/coordinators/trajectory_edit_coordinator.py:129) calls cancel on a different map. cancel drops the session without emitting a persistence command. tests/unit/test_trajectory_edit_coordinator.py:214 explicitly expects this loss, so existing coverage enforces the behavior KRT-26 must replace.
2. MapWidget._on_map_selected (src/gui/widgets/map_widget.py:1475) closes the properties editor and calls cancel_active_session before emitting map_selected. Managed vertex editing emits feature_geometry_cancel_requested, connected to FeatureGeometryCoordinator.cancel_edit. A prompt in the coordinator's map_selected listener alone would therefore be too late for geometry.
3. MapHandler.on_maps_ready (src/app/map_handler.py:491) repopulates the selector, resetting its index to -1, then restores the previous selection. That invokes _on_map_selected even for the same map and cancels geometry. Ordinary same-context refresh must preserve drafts without prompting.
4. FeatureGeometryCoordinator._start_session (src/app/coordinators/feature_geometry_coordinator.py:322) cancels the previous geometry session before starting another. Re-entering geometry editing or choosing a different Base/dated-state target also needs protection. Trajectory start_edit already refuses a different marker while active.
5. Geometry working vertices live in the scene item: apply_edit reads item._geometry (line 265). The session dictionary retains the target and before_states, but no independent updated vertex draft. Merely retaining this dictionary across a scene replacement cannot restore the working geometry.
6. Both cancel paths refuse cancellation while Apply is pending; map selection itself still proceeds. The proposed transition must wait for completion rather than interpreting a no-op cancel as permission to replace the scene. Trajectory Apply completes after its expected authoritative reload; geometry completes on its command result.

## Existing protections to retain

Trajectory authoritative reloads retain active work and detect conflicts (on_trajectories_ready). Geometry playback skips the active edited feature (_apply_for_map). Apply emits undoable commands; cancel does not persist. These are useful boundaries, but do not guard context replacement. The same-map marker diff can replace a changed scene item and deserves a focused draft-preservation check.

## Recommended implementation boundary

Add a feature-specific map edit transition coordinator with narrow dependencies on session owners, a decision presenter and approved navigation continuations. Gate requested selection before closing editors, cancelling sessions, changing the accepted map identity or starting replacement loads. Cover dropdown, parent/breadcrumb, detail-map and programmatic selection through one path.

- Keep editing: retain the accepted selection, scene, focus, playhead and complete draft; abandon requested navigation.
- Discard: explicitly cancel, then perform the requested transition.
- Apply: validate, submit through the existing command path, and continue only after successful session completion. Failure, conflict or incomplete trajectory keeps the session and original context. Disable/hold replacement requests during pending Apply; correlate completion to the session and requested transition.
- Same-map list refresh: restore selection without treating it as new navigation; preserve the current draft.
- Geometry target replacement: use the same decision before _start_session; snapshot current working vertices independently if scene replacement or stashing is supported.

Prefer the explicit decision for the first implementation. Stashing needs world/map/marker/target identity, updated vertices, draft suboperations and conflict handling; it is not equivalent to keeping the existing session dictionary.

Contract 5 directly requires this protection. Contracts 2/6/7/9 govern local keyboard ownership, visible mode/decision actions and consistent behavior. Keep nested trajectory date/equalization cancellation local. Use shared semantic presentation and run visual policy checks if UI changes. No contract revision is required.

## Acceptance verification for implementation

Exercise modified trajectory and Base/existing/new dated geometry against every navigation route; Keep editing, explicit Discard, successful Apply and failed Apply. Verify no database/history mutation before Apply, one undoable command for Apply, exact draft and viewport retention, same-map refresh, target replacement, invalid/incomplete trajectories and changes while Apply is pending. Check authoritative reloads, active-item replacement/deletion, and stale worker results. World switching, restore and application close also need lifecycle tracing: the inspected closeEvent guards Entity/Event drafts and pending raster strokes, but has no trajectory/geometry draft check.

## Validation limitation

Focused test execution was attempted for test_trajectory_edit_coordinator.py and test_feature_geometry_coordinator.py with QT_QPA_PLATFORM=offscreen. The .venv interpreter could not start: its configured WindowsApps Python 3.13 executable reported access denied. No pytest result or rendered walkthrough was obtained; findings above are current source traces. The shell runner also encountered setup-refresh failures; Node filesystem access allowed inspection to continue. No build, application fix or commit was performed.

## Implementation follow-up — 2026-10-08

The selected explicit-decision solution is implemented in the working tree.
[Verification and replay evidence](../evidence/krt26/README.md) record the guard,
working-copy ownership, lifecycle wiring and current checks. Unchanged existing
edits leave directly; new/modified drafts require a decision. The interpreter
access limitation above was resolved by running the project environment outside
the sandbox. No application build, commit or push was performed. KRT-26 remains
In Progress pending an authorized commit; assisted replay does not establish
human task time or first-use learnability.

## Publication follow-up — 2026-10-08

The user subsequently authorized commit and push. Publication details and the
final commit are recorded in KRT-26; the implementation delivery note above
describes the state before that authorization.
