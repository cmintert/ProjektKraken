# Kraken visual interaction vocabulary v1 — KRT-54

Published 2026-10-06. **Authority:** [Kraken visual interaction vocabulary v1](https://linear.app/projektkraken/document/kraken-visual-interaction-vocabulary-v1-6adef31c1900) in Linear Authoring UX.
**Repository counterpart:** `docs/ux/visual-interaction-vocabulary.md`. Deliberate revisions update both copies in the
same work batch. This complements [UI/UX Contract v1](authoring-contract.md);
it does not replace interaction rules or change inspector geometry.

## Meaning before appearance

The UI names meaning; the theme chooses appearance. All new or modified UI
presentation must use these roles, including work outside the initial
Entity/Event rollout. Semantic colors are not decorative emphasis.

| Meaning | Theme roles | Treatment |
| --- | --- | --- |
| Entity / Event identity | `entity_main`, `event_main` | Object identity, not supporting actions |
| Typed inline link | `link_entity`, `link_event` | Solid underline; tooltip identifies type and target |
| Unresolved or ambiguous target | `link_unresolved` | Dotted underline and explanation; content condition, not an application alarm |
| Loading, legacy untyped, external link | `link_neutral` | Neutral underline; explain loading or destination |
| Temporal/editing mode information | `mode_bg`, `mode_border`, `mode_text` | Neutral bordered banner with explicit editable/read-only wording |
| Warning / failure / completion | `warning`, `error`, `success` | State label or icon plus text; color never supplies the whole message |
| Selection / keyboard focus | `selection_bg`, `selection_text`, `focus_ring` | Selection stays distinct from identity; visible focus on every actionable control |
| Supporting / AI action | `supporting_text`, `supporting_caption` | Neutral quiet action; label/icon identifies AI |

The six existing palettes retain their background, surface, primary and object
identity colors. Link text, neutral captions and control boundaries have separate
theme mappings where those values do not meet contrast. There is no global palette
replacement. Built-in recovery palettes carry the same roles.

## Controls and states

Use `StyleHelper.get_action_role_style(role, selector)` or its existing primary,
secondary, tool and destructive compatibility helpers. Equivalent controls share
presentation rather than composing their own color scheme.

Ordinary buttons, labeled toolbar commands and overflow access share the secondary
role. Enabled secondary text uses each palette's `text_main`; backgrounds,
borders and interaction states use `action_secondary_*` tokens. Global QSS and
shared StyleHelper controls must agree. Input focus rules must not override action
borders. Primary, destructive and quiet/disclosure controls retain their own roles.

Vertical activity navigation buttons share an intrinsic width and height derived
from the largest current label. Recalculate the shared size after label, font or
style changes so the rail remains aligned and readable.

| Control role | Purpose | Affordance |
| --- | --- | --- |
| Primary | Principal apply/create action | Filled; not generic decorative emphasis |
| Secondary | Supporting operations and navigation | Neutral fill and visible boundary |
| Quiet / ghost | Low-priority disclosures and supporting writing actions | Neutral label, hover surface, visible focus and checked state |
| Destructive | Removal or irreversible intent | Destructive mapping plus explicit wording; retain existing guards |
| Inline link | Navigation within authored content | Underline and target meaning, not button chrome |

Every action role maps `action_<role>_<state>_<bg|text|border>` for normal,
hover, pressed, checked and disabled. Hover, pressed and checked refine normal;
keyboard focus wins over those states; disabled wins over interaction states.
Focused actions use a neutral secondary surface so the focus boundary has contrast.
Checked disclosures remain checkable and expose their expanded state.

Keep border thickness, padding and dimensions constant across states. Disabled
controls remain visibly button-like and explain prerequisites through tooltips.
Do not hide Open/Peek because the caret leaves a link. Narrow layouts use the
existing labeled More actions route, including disabled entries.
Long destination names may shorten when the full value remains accessible;
action wording must retain complete, unambiguous meaning under UI-GATE-01.
Tooltips and accessibility text do not justify clipped or truncated action names.
Availability tied to session history may still hide the Back action.

## Accessibility and context

Touched normal text meets 4.5:1 contrast; meaningful control boundaries and focus
indicators meet 3:1 against surrounding surfaces. Selection and mode-banner text
also meet 4.5:1. Disabled controls are exempt from WCAG contrast requirements,
but Kraken's mappings retain readable text and recognizable boundaries.
Transparent quiet controls work against application and editor surfaces.

Contracts 2/4/5/6/7/8/9 apply: preserve visible routes, focused-control keyboard
ownership, drafts, caret, scroll, playhead and undo/redo semantics. Theme changes
and target-snapshot refreshes are presentation, not authoring actions. Wiki cues
use transient highlighting rather than document edits. KRT-53 Save/Discard/Cancel
and hydration-based return behavior remains.

## Adoption and enforcement

UI plans, reviews and PR/direct-commit verification notes identify:

- Roles/shared helpers and applicable contract numbers.
- Enabled/disabled, focus, theme-switch and narrow-layout evidence.
- Context preservation and domain-justified exceptions.

Run `python -m scripts.check_visual_policy`. CI scans application/GUI Python and
production QSS for literal color decisions and local derivation, and checks role
completeness and contrast. Tests protect exact policy growth/removal, typed targets
and editing-history preservation.

`scripts/visual_policy_baseline.json` records exact existing expressions, counts,
source snippets and reasons. Legacy debt is not endorsement: migrate the touched
presentation path when next changing it. Authored raster/map palette values are
data, not UI colors; their exact reviewed exceptions remain independent of theme.
Do not exempt a whole widget, feature or directory.

Legacy styling must be unified or corrected at its next touch. The checker
compares changed function/method bodies and class/module constants against HEAD
locally, or the PR/push baseline in CI. A changed scope cannot retain legacy
exceptions; unrelated scopes and reviewed authored-data colors remain allowed.
Formatting/import-only changes do not trigger unrelated cleanup. A touched
production stylesheet must correct its remaining legacy literal colors.

New expressions, duplicate growth and stale entries fail. Remove reduced debt
explicitly. Any new exception explains its authored-data/domain need and related
issue in the change description. There is no automatic baseline update mode.
Review baseline diffs alongside code; do not regenerate to silence CI.

Static checks cannot determine whether a role means the right thing. Reviewers
must reject semantic misuse (for example, Entity blue on an AI action), even when
colors come from themes. Rendered evidence establishes presentation, not human
task-time improvement. KA-04/KA-20 remain relevant to empty-world comparisons.
## Timeline temporal grammar — 2026-10-07

KRT-50/KRT-57/KRT-58 extend this vocabulary to the world timeline.
This does not change stored temporal assertions or the authoring interaction contract.

- Occurrence marks answer when an event might start: precise points are filled;
  finite precision/occurrence windows use hollow anchors and caps; unbounded
  approximate dates use uncapped halos; one-sided assertions retain their hard
  cap and open direction. Hollow anchors are layout positions, not exact dates.
- For uncertain starts with a known duration, Starts, Duration and Possible span
  remain visible together. Duration is a detached length measure on a neutral
  surface; its horizontal placement does not assert a start/end date. Below six
  pixels it uses a broken compact measure and keeps the authored value visible.
- Possible span is a thin hatched possible-presence envelope with a solid
  guaranteed-presence core. It must not serve as the duration-length measure.
  Independently asserted endpoints show Starts, Ends and Possible span; their
  representative difference is not an authored fixed duration.
- Valid unbounded timing retains its occurrence grammar and explains that its
  presence span is not bounded. Question-mark marks indicate actual unresolved
  assertions or unavailable calendars.
- Collapsed group marks retain occurrence uncertainty with readable device-space
  strokes. Expansion and tooltips retain event names and authored duration.
- Viewing and World current time stay named in a pinned, wrapping date strip.
  The viewed-time mark is solid with a draggable handle; world time is dashed
  without a draggable handle. Separate identity rows below calendar ticks prevent
  label collisions. Coincident marks identify both roles.
- Snapping and event-directed navigation may use a representative position.
  Uncertain targets receive a disclosure after navigation safeguards accept;
  canceled/failed navigation retains the previous accepted context.
- Date captions use supporting_caption at full opacity. Definitely future
  occurrences show Not yet without dimming their names/dates. The existing
  past-start flag does not assert that a duration has finished.
- timeline_viewed_time and timeline_world_time are theme-owned time-identity
  roles, initially mapped to readable neutral text tokens; pattern, handle and
  text supply the distinction. timeline_grid and theme-owned halo/window opacity
  values control secondary geometry. event_main retains event identity; shared
  supporting text, selection and focus roles keep marks and controls readable.

Contracts 1/2/4/5/6/7/8/9 apply. Theme changes, accepted-target refresh and
collapsed-group refresh must preserve selection, drafts, playhead/world-time
separation and undo. Review normal/future, selected/unselected, focus, disabled,
hover/drag, six palettes and narrow overflow. Screenshot evidence establishes
rendering; fresh unprompted interpretation is required before claiming usability.

## Timeline dependency strands — 2026-10-28 (KRT-114)

- `timeline_dependency_0` through `timeline_dependency_7` identify connected
  chains of authored Follow Event timing references. All eight roles meet 3:1
  contrast against timeline backgrounds in every palette and recovery theme.
  They are categorical identity, not success, warning, chronology or Event type.
- Branches and merges share one strand color. The smallest Event UUID identifies
  a component, hashed deterministically into the eight slots. Colors may repeat;
  adding or removing a reference may recolor a merged or split chain. Hidden
  Events remain part of strand identity, so layout changes do not recolor it.
- Noninteractive curves meet event sides with horizontal endpoint tangents and
  arrowheads pointing from the source endpoint to the dependent endpoint.
  Endpoint rows and duration caps retain their temporal meaning. Detached
  duration measures never serve as endpoint ports; representative uncertain
  positions remain uncertain. Text, group headers and the ruler are protected.
- Output sockets use actual painted row/text extents rather than reserved label
  width. Prefer a single smooth cubic, with horizontal output/input handles.
  Obstructed routes use deterministic routing points and rounded, separated
  tracks. Sort branches by displayed source/target order and stable identities;
  penalize crossings and overlapping tracks without changing event placement.
  Route around text and marks instead of clipping out label-sized wire fragments.
  Ports and paths are presentation, not additional dates or authoring handles.
- Selection increases the width of incident connections without replacing their
  strand identity. Direction and endpoint geometry supplement color. Hidden or
  unresolved endpoint geometry does not acquire substitute group connections.
- Dependencies: [mode] is a contextual menu beside Snap to Events, with the same
  overflow route and Settings → Timeline synchronization. KRT-115 replaces the
  Boolean preference with All / Selected / Show dependency trail / Off. Selected
  is the fresh default; saved enabled/disabled choices become All/Off. Selected
  shows direct incident connections; Trail shows the entire selected Event's
  connected strand, including branches/merges across tag bands. Both show no
  connections without an accepted selected Event. Match strand identity, never
  the repeatable color slot. Route the full eligible set before filtering paint;
  changing mode or selection does not reshuffle paths. All Events remain visible
  under the existing timeline rules. The neutral secondary menu uses shared
  action/focus roles; strand colors retain categorical meaning. Preserve lane
  order, drafts, selection, keyboard ownership, Viewing/World current time and
  undo (contracts 1/2/4/5/6/7/8/9).
