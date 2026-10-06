# Projekt Kraken UI/UX Contract v1

**Version:** 1
**Published:** 2026-10-04
**Authority:** [Projekt Kraken UI/UX Contract v1](<https://linear.app/projektkraken/document/projekt-kraken-uiux-contract-v1-7354257ff07d>) in Linear.
**Repository counterpart:** `docs/ux/authoring-contract.md`.

The Linear document is authoritative. Deliberate revisions must update both copies in the same work batch, retain the version history, and state why the rule changed. Repository evidence and tests are linked from the audit; they do not silently redefine this contract.

## Purpose

This document is the normative interaction contract for Projekt Kraken. It exists to keep a sophisticated world model predictable to use as the application grows.

The contract does **not** reduce Kraken's temporal, relational, cartographic or analytical depth. It defines how that depth is revealed and manipulated.

## Core principle

**Make Kraken feel simpler without making Kraken simpler.**

The interface should express creator intent first and translate that intent into Kraken's richer internal model.

## Contract 1 — Progressive disclosure

* Present the common case first.
* Reveal advanced semantics only when the creator asks for them or the data requires them.
* Do not make uncommon edge cases permanently occupy the primary authoring surface.
* Advanced capability must remain reachable and lossless.

Positive references: text-first date entry, Date fields disclosure, Event has duration, End date / duration disclosure.

## Contract 2 — Interaction semantics

* Single click selects.
* Double-click opens or edits unless a documented surface-specific convention is stronger.
* Right-click exposes secondary actions; it must not be the only route to a core capability.
* Drag is reserved for spatial or structural manipulation where the relationship is visually understandable.
* Modifier keys are accelerators, never the sole discoverable path to functionality.
* Enter applies or commits the current local operation where appropriate.
* Escape cancels or exits toward the neutral/browse state.
* Delete requests deletion with the appropriate safety guard.

## Contract 3 — Authoring surfaces

* Inspectors handle ordinary editing.
* Modal dialogs are reserved for exceptional, multi-object or genuinely multi-step configuration.
* Frequent workflows should prefer direct manipulation with immediate visible feedback over modal configuration chains.
* A creator should not need to know which internal subsystem owns a fact in order to express it.

## Contract 4 — Creator language

Use worldbuilding language before implementation language.

Prefer:

* Became ruler
* Ended when this event happened
* Around 1218
* Date unknown
* Move here now

Avoid exposing terms such as temporal validity, evidence range or boundary mode unless the creator explicitly enters advanced controls or the distinction is necessary for correctness.

## Contract 5 — Context preservation

Navigation must not casually destroy creative state.

Preserve where practical:

* active selection,
* text cursor and selection,
* unsaved draft state,
* playhead position,
* map edit session,
* navigation origin/history.

When a context change would discard meaningful work, require an explicit Apply / Keep editing / Discard decision or an equivalent safe mechanism.

## Contract 6 — State and mode clarity

At any moment, the creator should be able to understand:

* what object is selected,
* what time is being viewed,
* whether the current state is editable or historical/read-only,
* whether a special editing mode is active,
* how to commit or cancel that mode.

Mode-specific controls should dominate while unrelated controls recede.

## Contract 7 — Discoverability

Every core capability needs a visible route.

Expert shortcuts, context menus and modifier gestures may accelerate a workflow but may not be required knowledge for discovering it.

Empty states should teach the next useful action rather than merely state that no content exists.

## Contract 8 — Consistency before local cleverness

Equivalent actions should behave consistently across Explorer, Entity/Event editors, Timeline, Map, Graph and Longform.

A local interaction may deviate only when the domain requires it, and the exception should be documented.

## Contract 9 — Feedback and reversibility

* Actions should produce immediate visible feedback.
* Destructive operations must be appropriately guarded.
* Undo/redo should preserve the creator's mental model of one action = one reversible operation where practical.
* Save/commit feedback must never steal the caret, overwrite a newer draft or silently alter authored meaning.

## Contract 10 — Complexity budget

Interaction complexity is treated as technical debt.

For benchmark tasks, track where practical:

* visible decisions,
* dialogs opened,
* panels/tabs visited,
* mode changes,
* hidden/modifier interactions,
* backtracking,
* errors,
* major hesitation points,
* terminology confusion.

Optimization must not make advanced/unusual workflows impossible. The goal is to remove **unnecessary** complexity.

## Validation rule

The contract is normative, but benchmark evidence can reveal that a rule needs refinement. Changes to the contract should be deliberate and documented rather than introduced implicitly by one widget.

## Initial audit targets

Apply this contract first to:

1. Relation authoring.
2. Entity/Event inspector information architecture.
3. Map mode behavior.
4. Wiki editor navigation/save lifecycle.
5. Timeline and graph interaction consistency.

## Definition of done for v1

* Major current surfaces have been inventoried against the contract.
* Known violations are either fixed, linked to an existing issue, or intentionally documented as justified exceptions.
* New UX work can cite this document as its design authority.
* The 20-task benchmark contains at least one advanced/unusual task that protects Kraken's expert workflows from over-simplification.

## Operational interpretation (v1, 2026-10-04)

* **Visible routes:** labeled controls, labeled disclosures, and a visible More actions menu qualify. Tooltips, right-click menus, and modifier gestures alone do not. Availability may depend on an explicitly selected object or mode; the prerequisite must be apparent.
* **Keyboard ownership:** Enter respects the focused control, including multiline text entry. Escape cancels the innermost active operation before leaving its containing mode. Cancelling a local draft must not discard unrelated edits.
* **Disclosure:** fresh common-case forms start collapsed. Existing advanced data must remain apparent and reachable; collapsing controls never removes values or changes authored meaning. A necessary structured-entry fallback is a documented exception, not a requirement to hide unusable primary input.
* **State retention:** reloading the same object preserves disclosure choices and drafts. Cross-object and cross-session persistence is evaluated per surface rather than imposed globally.
* **Exceptions:** record the behavior, domain justification, discoverable route, and evidence. Accidental drift remains a violation even when assigned to a follow-up issue.

## Review and evidence

New authoring changes identify the relevant contract numbers, visible entry points, keyboard ownership, context-preservation behavior, and justified exceptions. Use the existing shared presentation widgets before adding local patterns.

The repository audit is `docs/ux/authoring-interaction-audit.md`; the reproducible 20-task protocol is `docs/ux/authoring-benchmark.md`. This audit milestone establishes the inventory, baseline and safeguards. Measured creator improvement requires later before/after observations; an assisted walkthrough or automated test cannot establish that improvement.


## Visual vocabulary companion — 2026-10-06

All new or modified UI presentation also follows [Kraken visual interaction vocabulary v1](https://linear.app/projektkraken/document/kraken-visual-interaction-vocabulary-v1-6adef31c1900), with repository counterpart `docs/ux/visual-interaction-vocabulary.md`. It defines theme-owned semantic roles, shared control states, disabled affordance, focus, contrast and narrow-layout presentation. UI change notes identify roles, relevant contract numbers, verification and exceptions. This supplements Contract v1; its interaction rules remain unchanged.
