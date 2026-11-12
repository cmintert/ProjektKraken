# KRT-157 shared Markdown profile

Reviewed on 12 November 2026 against preservation commit `4275a1ca` and the
uncommitted parser migration in the regular checkout.

## Implemented contract

The four content readers use the shared CommonMark profile. Its explicit
extensions cover tables, double-tilde strikethrough, URL recognition, wikilinks
and existing footnote, definition-list and abbreviation reading behavior.
Single newlines stay visible. Parsing and link recognition operate locally.

Rich eligibility checks the parsed token vocabulary and the retained cursor
mapper's text representation. Other spellings remain in exact Source view.
Unedited Rich projections retain their original source. Source transitions use
original offsets, including extra blank lines and UTF-16 selections. Undo/Redo
continues through the retained presentation documents.

Authored HTML is separated from parser-generated navigation metadata before
sanitization. Safe formatting and table attributes remain readable. Existing
publication URL restrictions and destination-owned asset handling remain active.
DOCX rendering includes strikethrough and table alignment.

## Verification record

| Check | Result |
| --- | --- |
| Initial shared profile, export and publication regressions | 105 passed |
| Source mapping, AST and authoring regressions after offset correction | 166 passed |
| Final profile, paste and link-authoring selection | 90 passed |
| Installed dependency consistency | No broken requirements |
| Repository-wide typing | Clean in 666 source files; final repeat pending |
| Ruff, dependency projections, visual and complexity policies | Passed; final repeat pending |
| Official CommonMark 0.31.2 examples | 649 exact HTML matches; three equivalent empty-blockquote whitespace differences |
| Curated ci_fast suite | First concurrent run stopped during filesystem contention; sequential final run pending |
| Windows package | Build stopped after severe host memory pressure; final collection and two-launch smoke remain unverified |
| Strict Sphinx and offline Help | Passed; final reference correction rebuilt into offline Help |

The conformance comparison downloaded only public specification examples. The
runtime parser has no network client. Compatibility fixtures are independently
authored representative vocabulary, including Unicode, aligned/empty table cells,
wikilinks, literal code, quotes, lists and source-preservation cases.

The Windows contract requires complete notices for markdown-it-py, mdurl,
linkify-it-py and mdit-py-plugins. The package smoke exercises the parser's
features and validates the notice files. Build and review artifacts are isolated
under `artifacts/krt157-markdown-20261112/`.

The owner reported 95% memory usage and system-wide slowdown during packaging.
The task's build and waiting verification process trees were stopped. A subsequent
host check showed 22.9% memory usage and 47.6 GB free; no task-owned build or
verification processes remained. No peak per-process memory sample was captured,
so the precise cause is unconfirmed. The final build log reached replacement of
the interrupted candidate during collection, after both executables were built.
Packaging and broad verification must not be counted as passed.

## Documentation and interaction review

| Field | Evidence |
| --- | --- |
| Readers and purpose | Event/Entity writers and Longform publishers. Existing writing page is a how-to guide; the new Markdown profile is a reference. |
| Canonical pages | `docs/user/wiki-editor-markdown.md` and `docs/user/markdown-reference.md`, indexed in the manual and reference navigation. |
| Help destinations | Existing `help-writing-edit` anchor and inspection routes retained. The changed source getter was individually reviewed and fingerprinted. |
| Save and recovery | Existing Save Changes route, exact unedited source, supported semantic serialization after edits, local history and persistent command save/reopen tests. |
| Interaction contracts | Contracts 2/5/6/7/8/9/11. Existing Paste, Edit, View, Source notice, focus and Tab ownership remain the authoring routes. |
| Semantic presentation | Existing content typography and shared mode banner. No new control variant or identity-color meaning was introduced. |
| Rendered review | Desktop reading at 360/680 logical px in light/dark themes, Source editor at 360 px, generated offline reference and a PDF page inspected. Windows fonts were explicitly loaded for offscreen captures. A pipe-escaping error in the reference table was corrected. |
| Native acceptance | Pending. Offscreen captures do not establish native Windows DPI behavior. |
| Human documentation approval and reader testing | Pending. No participant outcomes are claimed. |
