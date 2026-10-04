# Authoring benchmark v1 — KRT-46

Published 2026-10-04. This is a **new 20-task catalog**, not recovered historical
benchmark code. [Contract v1](authoring-contract.md) is the design authority;
the [surface audit](authoring-interaction-audit.md) records the baseline violations.
The user will record human task videos later. Automated checks and the assisted
baseline do not establish creator completion time, hesitation or improvement.

## Fixture and reset

Use the repository-root `Rhine_Tribunal_UX_Benchmark_v1.krakenworld` archive.
SHA-256: `c66eb9095c7254f250021c7cb4d77d057ffef6c34236b139afa200ee9e940166`.
It contains a version-1 package manifest, portable world manifest, SQLite database
and `assets/maps/rhine_tribunal_benchmark.png`. Inspection found 47 entities,
20 events, one schematic map and 19 markers. The fixture's description mentions
historical baseline `022bc082`; **that is not the revision being benchmarked**.
Its names and positions are synthetic benchmark context, not canon or geography.

1. Launch with `start-kraken.cmd`. Use File → Import / Export… → World Transfer
   & Backups → Import a portable world as a new world → Choose package…
   and select the archive. Choose a fresh disposable destination name;
   never replace a personal world. Let the normal migration/recovery path complete.
2. Verify House Bjornaer, Severin of Falkenstein, Benchmark Tribunal Session 1187,
   Benchmark Winter Council 1201 and the Rhine Tribunal schematic map are present.
3. Record the application revision/version, Windows/Qt versions, theme, viewport,
   active calendar and initial playhead. Use the normal workspace and repeat
   layout-sensitive checks with approximately 360 px inspectors.
4. Perform KA-01–20 sequentially in the same working copy, using the outputs below.
   A facilitator may restore the prerequisites after a failed task; label that
   intervention and do not count the recovered task as unassisted success.
5. For another participant or a repeat run, close the world and import a **fresh
   copy** of the archive. Do not reset a database by copying over an open SQLite
   file or retaining old WAL files. Never mutate the original archive.

For a UI-independent setup, `src.services.world_transfer.import_world` accepts
the archive, destination root/name and a cancellation callback. Run it before
starting the application, then register/open the returned complete world folder.
It is fixture preparation, not an authoring-task shortcut.

## Task catalog

Read only the intention column to participants. The checks and recovery columns
are for the observer. Common tasks prefer visible routes; record every shortcut,
context menu or modifier used. Reaching a correct result through a hidden route
does not demonstrate visible-route compliance.

| ID | Creator intention | Prerequisites and semantic success | Allowed recovery |
| --- | --- | --- | --- |
| KA-01 | Create Tasgillia as a character. | Fresh fixture; new object has a UUID, name and deliberate Character type and opens as editing context. | Correct a silent Concept default; record the wrong initial type and correction. |
| KA-02 | Find Tasgillia again and resume editing. | KA-01; search/select the same UUID, with no duplicate creation or unintended draft loss. | Clear filters and search again. |
| KA-03 | Write that Tasgillia studies the Rhine's history. | KA-02; description saves and survives reopening. | Reopen the object; record any unsaved text loss. |
| KA-04 | Mention House Bjornaer in that description and follow the reference. | KA-03; link resolves the existing House Bjornaer, never a duplicate; return preserves origin/caret where supported. | Choose the matching completion or use Peek; record help. |
| KA-05 | Record that Tasgillia and House Bjornaer are connected, without deciding the details yet. | KA-04; one authored generic connection, separate from automatic WikiLink mentions. | Use the full Add Relation dialog; count its decisions and terminology. |
| KA-06 | Refine that connection into membership with a note. | KA-05; existing connection becomes member_of, with correct direction and preserved note; no duplicate relation. | Open full relation editing. |
| KA-07 | Make that membership begin at the date you are viewing. | KA-06; set playhead to the saved 1187 tribunal event first; fixed start equals playhead, visible date preview, no World Time change. | Explicit date entry is allowed; record extra navigation. |
| KA-08 | Record that Tasgillia's involvement in the 1201 winter council ends when that council happens. | Existing council and person; source-event relation has a dynamic end binding, and follows a later date change of the council. | Use event Relations and full timing controls; restore the council's original date after checking. |
| KA-09 | Create an event named Benchmark Charter 1218, known only to the year. | KA-08; event precision is YEAR, no invented month/day certainty and no implied duration. | Use structured Date fields; record assistance. |
| KA-10 | Mark that charter date as approximate. | KA-09; year precision plus approximate qualification survives save/reopen. | Use Date fields/qualification rather than memorized parser syntax. |
| KA-11 | Record that the charter meeting lasted three days. | KA-10; duration is three days independently from the approximate occurrence date; no certainty fabricated for the endpoint. | Use disclosed duration controls; record ambiguity. |
| KA-12 | View the world at the charter, then go to 1 January 1219. | KA-11; saved event date then exact active-calendar date become playhead; selection retained, World Time unchanged, normal temporal fanout. | Use Go to date; reject invalid input without leaving the dialog. |
| KA-13 | Place Tasgillia on the schematic map near Freiburg. | Person and map; marker references the existing person and has normalized position; no duplicate object/placement. | Add Marker/object picker or Explorer drag; record which route was found. |
| KA-14 | Draw a border for Upper Rhine, then revise one corner. | Unplaced Upper Rhine seed entity; closed polygon, linked to that entity, revised geometry persists; Enter applies and Escape cancels local work. | Use right-click Edit Vertices if necessary; explicitly record the missing visible route (KRT-48). |
| KA-15 | Give Tasgillia a journey from Freiburg toward Basel. | KA-13; two distinct timed positions, increasing dates, editable track; one Apply is one undoable change. | Use Edit Trajectory and guided Add Location; retain unsuccessful attempts in evidence. |
| KA-16 | Start changing that journey, then open a different map without losing the change. | KA-15; prepare a second disposable map using the same image; modify an unapplied working copy. Require Apply/Keep editing/Discard or safe restoration. | If lost, reconstruct only after recording failure (KRT-26); do not silently apply beforehand. |
| KA-17 | Inspect which connections are true at the date being viewed. | KA-07/08; graph At playhead excludes ended/not-yet-started edges; Show possible exposes uncertainty; selecting a node retains temporal context. | Refresh and select the appropriate relation filter; record empty-state guidance and help. |
| KA-18 | Assemble Tasgillia and the charter into a document, with the charter as a section, then reorder them. | KA-01/09; hierarchy/order persist and undo restores the previous arrangement. Missing visible membership setup is a failure, not a presumed inspector feature. | Facilitator may seed membership offline as below, then test organization separately. Context menu or promote/demote shortcut is recorded recovery (KRT-47). |
| KA-19 | Reopen the uncertain charter and the refined connection without changing their meaning. | KA-06/10/11; approximate year, three-day duration, relation notes/confidence and dynamic/fixed boundaries retained; opening/collapsing controls does not dirty data. | Reveal advanced controls; record which values were difficult to find. |
| KA-20 | Revise the charter's linked text, switch Rich/Source views, save, navigate away and return. | KA-09; exact supported source and link identity round-trip; save does not move caret or overwrite a newer draft; navigation safeguards resolve unsaved work. | Keep editing/Save/Discard must be deliberate; record source-mode fallback for unsupported rich syntax. |

### KA-18 facilitator recovery

First record the missing visible setup route. Close the disposable world and app.
Obtain the two existing object UUIDs from a lore export (File → Import / Export…
→ Export → JSON, All lore); never create substitute objects with the same names.
Run the existing CLI against that closed world's database, replacing the three
placeholders. Then reopen the world and observe organization without coaching:

```powershell
.venv\Scripts\python.exe -m src.cli.longform add --database "WORLD_DATABASE" --table entities --id PERSON_UUID --parent ROOT --position 100
.venv\Scripts\python.exe -m src.cli.longform add --database "WORLD_DATABASE" --table events --id CHARTER_UUID --parent ROOT --position 200
```

This uses the default document and existing command implementation. It is
assistance, not successful visible-route assembly. Reset through a fresh world
import before another run. The initial assisted render used seeded Severin and
the 1187 session to inspect the same outline operations, not persisted task-18
membership for Tasgillia and the charter.

## Recording protocol and result template

Record screens and spoken interpretation with participant consent. Do not coach
the discovery path. If a participant requests help, mark the point and describe
the intervention. For later comparison use the same catalog and fresh fixture,
record changed revision, and include KA-08/10/15/19/20 as depth protections.

Copy this record for **every** task, including failures:

```text
Run ID / date / revision / app version:
Participant or assisted mode / experience:
OS / Qt / theme / viewport / inspector width / calendar / initial playhead:
Fixture SHA-256:
Task ID / intended outcome:
Completion: unassisted | assisted | failed | not executed
Semantic correctness and verification:
Visible route and prerequisites:
Visible decisions / dialogs / panels / mode switches:
Shortcuts / right-click / modifier gestures used:
Backtracking / errors / wrong turns:
Context loss (selection, draft, caret, playhead, working copy):
Completion time / pauses / hesitation / terminology confusion:
Controls discovered easily / post-task interpretation:
Assistance / recovery:
Screenshot or video filename and timecodes:
Contract rules / issue links:
```

Use **not measured** for unavailable observations, never zero. Do not infer
human usability from tests, scripted inputs or source inspection. Keep positive
findings alongside problems; do not aggregate these diagnostics into one score.

The initial [assisted walkthrough](evidence/krt46/baseline.md) establishes source
and runtime evidence. Human video sessions remain the next measurement stage;
they may refine rules deliberately and prioritize the linked implementation issues.
