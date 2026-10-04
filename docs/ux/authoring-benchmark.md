# Authoring benchmark v1.1 — KRT-46

Published 2026-10-04; revised to v1.1 for empty-world human sessions. This is a
**new 20-task catalog**, not recovered historical
benchmark code. [Contract v1](authoring-contract.md) is the design authority;
the [surface audit](authoring-interaction-audit.md) records the baseline violations.
The user will record human task videos later. Automated checks and the assisted
baseline do not establish creator completion time, hesitation or improvement.

## Human video sessions: empty world and reset

Every human run starts from a **new empty world**, as requested by the user.
There must be no authored entities, events, relations, maps, markers or Longform
content. Default calendar/schema metadata is allowed; it is not seeded lore.
Do not import the Rhine Tribunal world, reuse an assisted probe database, or
prepopulate later task dependencies.

1. Start recording before world setup. Launch with `start-kraken.cmd`. Use File
   → Manage Databases… → Create New, give the disposable world a unique name,
   and use Select & Restart to open it. Record setup separately from task times.
2. Show the empty Explorer/authoring surfaces. Confirm no authored content exists;
   record any unexpected defaults rather than quietly deleting them off camera.
3. Record catalog v1.1, application revision/version, Windows/Qt versions, theme,
   viewport, active calendar and initial playhead. Use the normal workspace and
   repeat layout-sensitive checks with approximately 360 px inspectors. The date
   examples assume the default Gregorian calendar; record any calendar setup.
4. Perform KA-01–20 sequentially in the same working copy, using the outputs below.
   Supporting objects are created on camera within the specified tasks. If an
   earlier failure blocks a later task, record that dependency failure before
   facilitator recovery; label any recovered task as assisted.
5. For another participant or repeat run, create another **new empty world**.
   Keep the previous run for evidence. Do not reset by deleting personal worlds
   or copying over an open SQLite database.

A static map background may be supplied as an external input file before the
session, with its filename/SHA-256 recorded. It contains no application objects;
the participant creates/imports the map during KA-13. Reuse the same image for
comparable sessions. The schematic PNG inside the Rhine archive is an optional
image source: extract only `assets/maps/rhine_tribunal_benchmark.png`, not its
database/world manifest. No maps or locations are created before recording.

### Earlier assisted audit fixture

The already-recorded [assisted baseline](evidence/krt46/baseline.md) used catalog
v1 and the repository-root `Rhine_Tribunal_UX_Benchmark_v1.krakenworld` archive,
SHA-256 `c66eb9095c7254f250021c7cb4d77d057ffef6c34236b139afa200ee9e940166`.
It contains 47 entities, 20 events, one schematic map and 19 markers. Its
description mentions historical baseline `022bc082`, not the audited revision.
That seeded run remains source/runtime audit evidence. It is not an empty-world
human baseline and must not be pooled with v1.1 human task timings or completion
rates. Its import route is File → Import / Export… → World Transfer & Backups
→ Import a portable world as a new world → Choose package….

## Task catalog

Read only the intention column to participants. The checks and recovery columns
are for the observer. Common tasks prefer visible routes; record every shortcut,
context menu or modifier used. Reaching a correct result through a hidden route
does not demonstrate visible-route compliance.

| ID | Creator intention | Prerequisites and semantic success | Allowed recovery |
| --- | --- | --- | --- |
| KA-01 | Create Tasgillia as a character. | New empty world; new object has a UUID, name and deliberate Character type and opens as editing context. | Correct a silent Concept default; record the wrong initial type and correction. |
| KA-02 | Find Tasgillia again and resume editing. | KA-01; search/select the same UUID, with no duplicate creation or unintended draft loss. | Clear filters and search again. |
| KA-03 | Write that Tasgillia studies the Rhine's history. | KA-02; description saves and survives reopening. | Reopen the object; record any unsaved text loss. |
| KA-04 | Create House Bjornaer as a group, mention it in Tasgillia's description and follow the reference. | KA-03; create the group on camera; link resolves that same UUID, never a duplicate; return preserves origin/caret where supported. | Choose the matching completion or use Peek; record help and any interrupted writing. |
| KA-05 | Record that Tasgillia and House Bjornaer are connected, without deciding the details yet. | KA-04; one authored generic connection, separate from automatic WikiLink mentions. | Use the full Add Relation dialog; count its decisions and terminology. |
| KA-06 | Refine that connection into membership with a note. | KA-05; existing connection becomes member_of, with correct direction and preserved note; no duplicate relation. | Open full relation editing. |
| KA-07 | Record a tribunal session on 1 January 1187, view the world there, and make that membership begin at the date being viewed. | KA-06; create and save the session on camera; fixed membership start equals playhead, visible date preview, no World Time change. | Explicit date entry is allowed; record event setup separately from membership refinement. |
| KA-08 | Record a winter council on 1 January 1201 and make Tasgillia's involvement end when that council happens. | Create/save the council on camera; source-event relation has a dynamic end binding, and follows a later date change of that same council. | Use event Relations and full timing controls; restore the council's original date after checking. |
| KA-09 | Create an event named Benchmark Charter 1218, known only to the year. | KA-08; event precision is YEAR, no invented month/day certainty and no implied duration. | Use structured Date fields; record assistance. |
| KA-10 | Mark that charter date as approximate. | KA-09; year precision plus approximate qualification survives save/reopen. | Use Date fields/qualification rather than memorized parser syntax. |
| KA-11 | Record that the charter meeting lasted three days. | KA-10; duration is three days independently from the approximate occurrence date; no certainty fabricated for the endpoint. | Use disclosed duration controls; record ambiguity. |
| KA-12 | View the world at the charter, then go to 1 January 1219. | KA-11; saved event date then exact active-calendar date become playhead; selection retained, World Time unchanged, normal temporal fanout. | Use Go to date; reject invalid input without leaving the dialog. |
| KA-13 | Create a map from the supplied image and place Tasgillia near Freiburg. | KA-01 and external image only; create the map on camera; marker references the existing person and has normalized position; no duplicate object/placement. Freiburg/Basel are image landmarks, not precreated world objects. | Add Marker/object picker or Explorer drag; record map setup separately from placement. |
| KA-14 | Create Upper Rhine as a region, draw its border, then revise one corner. | Create the region on camera; closed polygon linked to that UUID; revised geometry persists; Enter applies and Escape cancels local work. | Use right-click Edit Vertices if necessary; explicitly record the missing visible route (KRT-48). |
| KA-15 | Give Tasgillia a journey from Freiburg toward Basel. | KA-13; two distinct timed positions, increasing dates, editable track; one Apply is one undoable change. | Use Edit Trajectory and guided Add Location; retain unsuccessful attempts in evidence. |
| KA-16 | Create a second map, start changing that journey on the first, then open the second without losing the change. | KA-15; create the second map on camera using the same image; modify an unapplied working copy on the first. Require Apply/Keep editing/Discard or safe restoration. | If lost, reconstruct only after recording failure (KRT-26); do not silently apply beforehand. |
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
assistance, not successful visible-route assembly. Reset through a new empty
world before another human run. The initial assisted render used seeded Severin and
the 1187 session to inspect the same outline operations, not persisted task-18
membership for Tasgillia and the charter.

## Recording protocol and result template

Record screens and spoken interpretation with participant consent. Do not coach
the discovery path. If a participant requests help, mark the point and describe
the intervention. For later comparison use catalog v1.1 and a new empty world,
record changed revision, and include KA-08/10/15/19/20 as depth protections.

Copy this record for **every** task, including failures:

```text
Run ID / date / catalog version / revision / app version:
Participant or assisted mode / experience:
OS / Qt / theme / viewport / inspector width / calendar / initial playhead:
Starting condition / empty-world evidence / setup video timecodes:
External map image filename / SHA-256 (if used):
Task ID / intended outcome / dependency setup timecodes:
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
