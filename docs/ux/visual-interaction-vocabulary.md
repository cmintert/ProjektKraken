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
existing labeled More actions route, including disabled entries. Long return
labels shorten with the full destination retained in tooltip/accessibility text.
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
