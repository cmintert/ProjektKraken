# KRT-159 portable note links

Markdown strategy step 4, implemented on 12 November 2026 after table-authoring
commit `9313011b`. Delivery is recorded in the linked Linear issue.

## Scope and identity contract

The recovered original gap analysis sequenced preservation, a shared syntax
contract, visual tables, then portable link conversion. This milestone completes
that conversion for native Obsidian note descriptions. Candidate extensions such
as callouts and embeds are not added by this milestone.

Filename allocation precedes body conversion. Stable-ID links and unique authored
names resolve to the actual exported note targets. The reviewed export snapshot
retains world-wide name candidates, so selecting one duplicate does not erase the
other candidate. Filename sanitization avoids Obsidian target delimiters and
Windows device names; original record names remain in native metadata.

Only referenced converted destinations are stored in each native note's
`kraken.link_targets` map. Unresolved targets are recorded separately. If a
converted link would collide with an unresolved name, the explicit filename
including `.md` is used; if both spellings collide, export fails explicitly.
Native reimport never guesses an identity for a preserved unresolved target.

Exact untouched descriptions are restored through the existing body-projection
contract. When the body is edited, known exported targets regain stable IDs while
prose and aliases retain the edits. Ordinary `.md` and case variants of known
targets are accepted unless they were preserved unresolved. Unknown targets stay
authored. Renamed note destinations and new links outside the per-note map are
not automatically reconciled. Unresolved names can have Obsidian's own vault
semantics; preservation does not claim an unambiguous external destination.

The shared syntax identifies semantic wikilinks before source replacement.
Tables escape alias pipes; prose, quotes, lists and compatibility footnotes retain
their structure. Inline/fenced/indented code, escaped examples, HTML attributes,
HTML code elements and embeds remain literal. No live world records or asserted
Relationships are changed by export. Reimport retains the reviewed transfer
command and its persistent Undo path.

The syntax follows Obsidian's
[internal link documentation](https://obsidian.md/help/links) and
[table alias rules](https://obsidian.md/help/Editing+and+formatting/Advanced+formatting+syntax).
Only public documentation was consulted; runtime conversion is local.

## Verification and limits

Focused tests cover allocated/sanitized/duplicate filenames, Entity/Event and
single-note targets, edited and unchanged import, ambiguous original names,
selected export, literal examples, Unicode aliases, GFM cells, compatibility
footnotes and command Undo. The final bounded selection passed 193 tests.
Repository Ruff and mypy (669 source files), complexity, visual and Help
inspection checks passed. Earlier focused selections overlap and are not added
to that count.
Strict Sphinx and offline Help generation passed. The new procedure was rendered
and inspected in the production Help viewer in light/dark themes at 720 logical
pixels, and in the generated manual through a disposable Qt WebEngine view at
1100 pixels with remote requests blocked. Captures are retained locally under
`artifacts/krt159/`. The final host memory check showed 24% used and 46.9 GB free.
No package rebuild or full regression is claimed. Native Obsidian interaction
and independent human acceptance remain pending.

## Documentation and interaction review

The existing import/export page remains the canonical how-to. The Markdown
profile remains a reference. The procedure covers prerequisites, export scope,
editing, reviewed Merge/Replace, the accepting import action, Undo and limits.
Existing Import/Export routes, review choices and Help meanings are unchanged.
There is no new UI presentation, keyboard owner or contract exception; the
existing draft/review and reversibility contracts 5/9 remain in force.

[Documentation review](../../../developer/documentation-review.md) and
[reader observations](../../../developer/documentation-reader-testing.md) are
separate from automated validation. Rendered documentation and human approval
are recorded separately; no participant results are claimed.
