# KRT-82 — Product-owner native acceptance

Date: 2026-10-12. Reviewer and decision owner: Christian.

The owner supplied four native Windows screenshots in the Codex conversation,
marked 100%, 125%, 150% and 200%, then explicitly instructed:

> I would just use the screens as evidence, mark it off and move on

Decision: accept these screenshots as sufficient native evidence for closing
KRT-82. The owner accepts the constrained workspace at 150% and 200%; reduced
visible content and scrolling alone are not action-label failures.

The captures show the Northwatch Demo, a light theme, Project Explorer, Entity
Overview/writing controls, Graph and Timeline. Visible Save/Discard actions remain
direct and readable at all four marked scales. No confirmed action-label failure
was established from these captures. At 200%, writing controls extend below the
inspector viewport; their scrolled state and opened overflow destinations were
not supplied.

The screenshot title reports revision `75ace9b8`; the implementation is committed
through `8046be0c`. The running application's exact source state is unconfirmed.
OS scales are owner-provided annotations. Actual Qt logical client dimensions,
font/text scale, and screenshot hashes were not independently recorded. Images
remain in the conversation; this document is the durable acceptance record,
not a local archive of the original screenshot files.

This is an explicit reduction of the native review scope for issue closure.
It is not a claim of native coverage for every registered surface, theme,
independent text factor or contextual state. Automated evidence retains its
existing recorded revision boundaries. The strict release-preflight manifest
remains incomplete and its validation logic is unchanged; a release-preflight
pass is not represented by this acceptance decision.
