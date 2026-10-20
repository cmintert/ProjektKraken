# 0.20.0 beta 1 release preparation

Preparation date: 20 October 2026. Source baseline: `d947f900` plus the staged
version bump and release preparation. This is an uncommitted candidate, not a
publication approval. Final package evidence must identify the committed source
and the exact ZIP SHA-256.

Tracked by KRT-100 under the KRT-19 publication task.

Public release notes and itch.io copy are prepared for the eventual verified
release. Their availability does not approve publication; the verification
status and outstanding gates are recorded here.

## Architecture guard review

The first full-regression attempt stopped at the DatabaseService API guard. A
separate architecture selection reproduced two failures: an unregistered
`DatabaseService.require_connection` method and a worker size of 2,115 lines
against the historical 2,089-line warning budget.

`require_connection`, introduced in `d78362c8`, returns only an already-open
connection on its owning thread and raises for disconnection or wrong-thread
access. `get_connection` delegates to it. This is an explicit persistence/thread
ownership boundary, not a new feature responsibility. The reviewed API is now
listed individually; the addition-only guard remains in force for other APIs.

Worker changes since the recorded baseline cover existing initialization,
migration reporting and failure cleanup, shutdown acknowledgement, command
tracing, and event/entity/map load failures. Domain migration and mutation work
remain delegated to their existing services and commands. Public worker methods
already pass the API guard. Retain the original 1,990-line reference and set an
explicit reviewed maximum of 2,115 lines. This admits the current infrastructure
fixes without granting another five-percent growth budget. Other choke-point
budgets and the complexity policy remain unchanged. Future worker growth must
extract a capability or receive another explicit review.

## Regression maintenance

The next full run found a WAL-isolation test calling the removed private
`_init_schema` method and expecting a refresh to end a caller-owned transaction.
The corrected test uses public connection access, commits the writer explicitly,
checks that refresh retains the reader's active snapshot, then verifies newly
committed data after the reader's owner ends that transaction. Both services
close on every exit path. The combined architecture/isolation selection passes
12 tests.

The next run found that the unsaved-change test's partial window/editor doubles
did not implement current Event navigation and wiki-link interfaces. Its purpose
is the unsaved-change decision, not complete window startup. The correction uses
the real MainWindow delegation method and real EditorCoordinator with a small
parent widget and editor. Clean, Save, Discard and Cancel retain their original
assertions without starting database workers or unrelated panels.

The complete coverage run stopped reporting progress before an application-wide
theme probe, with an active test process and working set above 2 GB. It was
stopped deliberately; its partial log is not a completed regression result.
Component theme tests now route palette and stylesheet application to their own
probe widget instead of restyling all widgets retained by the serial suite.
ThemeManager signals, formatted production
QSS, rendered colors, links, drafts, undo and context assertions remain exercised.
The native-panel test additionally checks the real QApplication palette for both
themes and asserts the global stylesheet stays unchanged. The final combined
release-fix selection passes 267 tests in 90.20 seconds. This is focused
verification, not a completed full-regression or native performance comparison.
Theme-sensitive component modules also use the shared `isolated_theme_manager`
fixture. It creates a real manager from production themes for each test and
restores the previous singleton after deferred widget cleanup. This isolates
signal receivers from earlier serial tests. The fixture does not pre-apply a new
application stylesheet to a bare text editor, preserving the original HTML and
undo assertions. The isolated combined selection passes 267 tests in 89.48
seconds. No production presentation behavior changed.

The restarted complete run found an auto-refresh test still expecting Event
creation to reload all data. The existing creation fallback deliberately reloads
only Events to preserve unrelated drafts. The corrected test waits for that
dataset signal and verifies no full reload, while retaining the full-reload
assertion for a legacy Entity update and all Longform toggle assertions.

The subsequent serial run terminated in a typography test without a final
summary. A focused reproduction identified a click on a missing toolbar widget:
heading actions now live in the Headings menu. The test now clicks that menu's
H3 action and retains the rendered-height, character-size and Markdown assertions.
Two typography input dictionaries now include the required semantic link/text
tokens while continuing to test numeric defaults independently.

The old Sprint 0 drop tests also expected whole-inspector drops to save relations
immediately. Authoring contract 12 requires a labeled Connections target and
explicit Connect / Cancel. The corrected cases verify that whole-inspector drops
do nothing, a complete drag-enter/drop stages without emitting a request, and
Connect emits exactly one request with the original directed IDs and attributes.
Both modules pass all 15 tests; no application code changed.

At the owner's request, passing tests are now reused instead of restarting the
whole suite. `resume_regression.py` in the local artifact directory selects only
cases without a recorded pass. `reused-passes.json` maps each reused case to its
source log, and `remaining-cases.json` records the continued selection. These
combined local results are not a single completed coverage run. The exact clean
candidate still requires the complete remote regression and coverage job.

The remaining-case continuation completed with 2,979 passes, two skips and 15
failures. All 15 failures now have focused passing evidence. Corrections cover
the map-transition dependency in the database-manager double, real Qt preview
controls with only modal execution intercepted, current semantic identity/link
and disabled-control roles, exact authored wiki-label whitespace, and automatic
Longform inclusion in the unauthenticated local viewer.

Responsive toolbar probes now apply the production stylesheet. Focus restoration
waits for the fixture's initial adaptive layout to settle before recording its
splitter width; the transient vertical scrollbar accounted for the 14-pixel
difference. The Project controls already live on a scrollable page. Its regression
now compares geometry in that page's coordinates and verifies the overflow
button can be scrolled into view, retaining complete labels and action routes.
These apply contracts 5/7/8 and the existing semantic vocabulary without changing
application presentation or interaction behavior. Automated offscreen probes do
not establish native readability or human acceptance.

The audited combined ledger accounts for all 6,838 collected cases: **6,833
passing and five existing platform/environment skips**, with no uncovered cases.
`combined-regression-ledger.json` maps outcomes to evidence and
`combined-regression-summary.json` records the totals. Passing tests were reused
as requested. This is combined regression evidence, not a completed single-process
full-suite or coverage result. Earlier native process terminations remain a
serial-run limitation; the circuit-breaker test at one termination point passed
alone. The clean committed-source remote full regression/coverage gate is still
required before tagging.

## Verification and acceptance

Local preparation reports are retained under
`artifacts/release-0.20.0-beta1/`. The initial 11-check preflight passed, including
2,402 tests with three skips. Both About-dialog tests passed. The executable
built successfully with FileVersion `0.20.0` and ProductVersion `0.20.0 beta1`.
The Help-only executable probe passed for 12 pages and 1,031 search documents.
These results precede the architecture-guard correction; full-regression
results must be recorded separately after that correction.

## Local rehearsal package

The preserved direct-spec build was copied into a separate staging directory.
The rehearsal strips nested test directories, retains the GPL text at the package
root, and checks required files, forbidden development packages/Python executables,
archive path lengths, x64 PE identity, and Help/package identity. Those checks
pass. The ZIP contains one `ProjektKraken` root with 13,963 files; every archive
entry passes its CRC check.

- Archive: `artifacts/release-0.20.0-beta1/candidate/ProjektKraken-0.20.0-beta1-windows-x64.zip`
- Size: 470,706,873 bytes.
- SHA-256: `6bf768a16f1afd7f0bda777d1e874d308b6d5f7ac0d0229e69f553e02e9a0228`.
- Build metadata: baseline `d947f900d0874df8ab7a70ef3ae118d577281bac`,
  `source_dirty: true`.

This is a rehearsal artifact, not the final distributable. The final clean CI
candidate needs its own checksum, two-launch smoke, dependency audit and
acceptance record. No runtime logs or personal worlds are included in this ZIP.

## Remaining release gates

The native label-review validator reports pending approval. The narrower
[KRT-82 owner acceptance](../ux/evidence/krt82/native-acceptance.md) does not
complete the strict release manifest. Do not fabricate records or change the
manifest to approved from automated captures. The full action-label matrix and
the required native evidence remain release gates.

The packaged smoke script starts with `--reset-settings` and uses the regular
application settings identity. Run its two launches in a disposable Windows
account or VM, not in a developer account with active personal settings. Keep
the exact ZIP and clean-VM evidence with the candidate. Complete the data-trust,
Help workflow and diagnostic checks tracked by KRT-44, KRT-91 and KRT-66.

## Delivery sequence

1. Review the combined local regression evidence and outstanding acceptance gates.
2. Approve and create the release-preparation commit, then authorize its push.
3. Run the current remote full-regression fallback on that exact commit:
   `gh workflow run tests.yml --ref main -f full_regression=true`.
   Confirm the workflow run's head SHA equals the candidate commit and its
   **Release verification** aggregate passes with complete coverage. The workflow
   remains **Smoke CI**; its manual full path uses six shards and fresh module
   processes. Follow [isolated release regression](release-regression.md) for
   retained evidence and reviewed same-run recovery. Partial prior results do not
   validate this candidate.
4. Create the lightweight `0.20.0-beta1` tag on the verified commit only after
   tagging is authorized. Push the tag only when explicitly authorized.
5. The tag runs **Windows Beta Package**. Retain its ZIP, checksum and smoke
   reports; complete native and clean-VM acceptance for that exact CI ZIP.
6. Approve the protected `windows-beta` environment only after acceptance. Its
   publication job creates or updates the GitHub prerelease from the checked-in
   release notes and uploads the ZIP and checksum.
7. Use the matching paste-ready itch.io copy only when the same verified
   downloads are available. Confirm public download/version/checksum links.

GitHub configuration was inspected on 20 October 2026: `windows-beta` requires
one reviewer, and the Smoke CI, Windows Beta Package and documentation workflows
are active. Remote `main` was `51be123171ff0ae38488e5a7bad65294bb8b30da`, five
commits behind local baseline `d947f900` before this release commit. A future push
includes those five existing commits as well as the release-preparation commit.
