# Authoring benchmark v1.2 — KRT-46

Published 2026-10-04; v1.1 introduced empty-world human sessions; v1.2 clarifies
participant wording after the first KA-01–15 video review. This is a
**new 20-task catalog**, not recovered historical
benchmark code. [Contract v1](authoring-contract.md) is the design authority;
the [surface audit](authoring-interaction-audit.md) records the baseline violations.
The first [human video review](evidence/krt46/human-run-1.md) records KA-01–15
under v1.1, with partial outcomes and evidence limits. Automated checks and the
assisted baseline do not establish creator completion time, hesitation or improvement.

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
3. Record catalog v1.2, application revision/version, Windows/Qt versions, theme,
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

Give one task at a time in English, using the intention below verbatim. Describe
the desired lore and outcome, not the buttons, syntax or gestures to use. Ask the
participant to think aloud; give route guidance only as recorded assistance.
Let the participant report completion before performing observer checks. Record
check-driven corrections separately from the initial attempt.

In KA-02/03, deselecting and reopening Tasgillia is sufficient navigation in the
empty world; no extra lore object is required. In KA-13/15, Freiburg and Basel
are places on the supplied image, not objects the participant must create.
If the image lacks those landmarks, identify their positions before timing the
map tasks and record that setup.

Keep the first video's KA-01–15 results under v1.1. A continuation using revised
KA-16–20 prompts is a mixed-version run: record v1.2 for those tasks and any
dependency recovery. Do not relabel earlier attempts or pool their timings with
fresh v1.2 runs. Observer success criteria remain unchanged; the wording makes
the intended outcomes and verification steps explicit.

| ID | Creator intention | Prerequisites and semantic success | Allowed recovery |
| --- | --- | --- | --- |
| KA-01 | Create a character named Tasgillia. | New empty world; new object has a UUID, name and deliberate Character type and opens as editing context. | Correct a silent Concept default; record the wrong initial type and correction. |
| KA-02 | Leave Tasgillia's editor, then find the same character again and resume editing her. | KA-01; search/select the same UUID, with no duplicate creation or unintended draft loss. | Clear filters and search again. |
| KA-03 | Write in Tasgillia's description that she studies the history of the Rhine. Finish the edit, leave her editor and return to check that the text remains. | KA-02; description saves and survives reopening. | Reopen the object; record any unsaved text loss. |
| KA-04 | Create a group named House Bjornaer. Write about it in Tasgillia's description and link the group's name to its existing entry. Follow that link to open House Bjornaer, then return to your writing. | KA-03; create the group on camera; link resolves that same UUID, never a duplicate; return preserves origin/caret where supported. | Choose the matching completion or use Peek; record help and any interrupted writing. |
| KA-05 | Separately from the link in her description, record a connection between Tasgillia and House Bjornaer. You know they are connected, but have not yet decided what kind of connection it is. | KA-04; one authored generic connection, separate from automatic WikiLink mentions. | Use the full Add Relation dialog; count its decisions and terminology. |
| KA-06 | You now know that Tasgillia is a member of House Bjornaer. Update the connection you just recorded to express that membership, and add a note explaining it. | KA-05; existing connection becomes member_of, with correct direction and preserved note; no duplicate relation. | Open full relation editing. |
| KA-07 | Create an event named Tribunal Session on 1 January 1187 and view the world at that date. Set Tasgillia's membership in House Bjornaer to begin on the date you are viewing. That membership start should stay on this date even if the session is later rescheduled. | KA-06; create and save the session on camera; fixed membership start equals playhead, visible date preview, no World Time change. | Explicit date entry is allowed; record event setup separately from membership refinement. |
| KA-08 | Create an event named Winter Council on 1 January 1201. Record Tasgillia as a participant in this council, with her participation ending when the council happens. If the council is rescheduled, her participation's end should move with it. Reschedule the council to 1 January 1202 to check this, then restore it to 1 January 1201. | Create/save the council on camera; source-event relation has a dynamic end binding, and follows a later date change of that same council. | Use event Relations and full timing controls; restore the council's original date after checking. |
| KA-09 | Create an event named Benchmark Charter 1218. You know it happened sometime in 1218, but do not know the month or day. | KA-08; event precision is YEAR, no invented month/day certainty and no implied duration. | Use structured Date fields; record assistance. |
| KA-10 | You now learn that even the charter's year is an estimate. Mark its date as approximately 1218, still without a known month or day. Finish the edit and reopen the event to check that meaning. | KA-09; year precision plus approximate qualification survives save/reopen. | Use Date fields/qualification rather than memorized parser syntax. |
| KA-11 | Record that the charter meeting lasted three days. Its occurrence date should remain approximately 1218, with no known month or day. | KA-10; duration is three days independently from the approximate occurrence date; no certainty fabricated for the endpoint. | Use disclosed duration controls; record ambiguity. |
| KA-12 | View the world at the charter's recorded date, then view it at exactly 1 January 1219. Keep the charter selected. You are exploring these dates, not changing the world's current date. | KA-11; saved event date then exact active-calendar date become playhead; selection retained, World Time unchanged, normal temporal fanout. | Use Go to date; reject invalid input without leaving the dialog. |
| KA-13 | Create a map using the supplied image. Place the existing Tasgillia character near Freiburg on that map. | KA-01 and external image only; create the map on camera; marker references the existing person and has normalized position; no duplicate object/placement. Freiburg/Basel are image landmarks, not precreated world objects. | Add Marker/object picker or Explorer drag; record map setup separately from placement. |
| KA-14 | Create an entry named Upper Rhine to represent a geographic region. Draw its closed border on the map, then change one corner at the requested viewing date. Finish the change, view another date, return and reopen the map to check that the revised border remains. | Create the region on camera; closed polygon linked to that UUID; use visible controls alone; dated revision persists without changing Base; Enter applies and Escape cancels local work. | Feature actions in Map or Layers now supplies the visible route (KRT-48). Record any facilitator guidance or right-click recovery separately; neither proves unassisted discovery. |
| KA-15 | Record a journey for Tasgillia from near Freiburg toward Basel. Give her a starting position on one date and a different position on a later date. Finish recording the journey, check that you can edit it again, then undo the recorded journey and redo it so it is available for the next task. | KA-13; two distinct timed positions, increasing dates, editable track; one Apply is one undoable change. | Use Edit Trajectory and guided Add Location; retain unsuccessful attempts in evidence. |
| KA-16 | Create a second map using the same image. On the first map, begin changing Tasgillia's saved journey but leave the change unfinished. Open the second map, then return to the first. You want to retain the journey edit: describe any decision offered and check whether you can continue with your change. | KA-15; create the second map on camera using the same image; modify an unapplied working copy on the first. Require Apply/Keep editing/Discard or safe restoration. | If lost, reconstruct only after recording failure (KRT-26); do not silently apply beforehand. |
| KA-17 | In the graph, inspect which recorded connections are true at the date you are viewing. Also inspect connections that might be true because their timing is uncertain. Select a connected object while keeping the same viewing date. | KA-07/08; graph At playhead excludes ended/not-yet-started edges; Show possible exposes uncertainty; selecting a node retains temporal context. | Refresh and select the appropriate relation filter; record empty-state guidance and help. |
| KA-18 | Assemble Tasgillia and Benchmark Charter 1218 into a document, with the charter presented as a section. Change their order, leave the document and return to check the arrangement. Undo the reorder and check that the previous arrangement returns. | KA-01/09; hierarchy/order persist and undo restores the previous arrangement. Missing visible membership setup is a failure, not a presumed inspector feature. | Facilitator may seed membership offline as below, then test organization separately. Context menu or promote/demote shortcut is recorded recovery (KRT-47). |
| KA-19 | Reopen the charter, Tasgillia's membership in House Bjornaer and her participation in Winter Council. Inspect their dates, duration and relation details without changing them. Check that the charter is still approximately 1218 and lasts three days, the membership retains its note and fixed start, and the council participation retains its event-linked end. | KA-06/10/11; approximate year, three-day duration, relation notes/confidence and dynamic/fixed boundaries retained; opening/collapsing controls does not dirty data. | Reveal advanced controls; record which values were difficult to find. |
| KA-20 | In the charter's description, write a sentence mentioning Tasgillia and make the mention open her existing entry. Revise that sentence, inspect it in both Rich and Source views, and finish the edit. Leave the event and return to check that your text and the link still work. Also try leaving with another edit unfinished and deliberately decide what should happen to that edit. | KA-09; exact supported source and link identity round-trip; save does not move caret or overwrite a newer draft; navigation safeguards resolve unsaved work. | Keep editing/Save/Discard must be deliberate; record source-mode fallback for unsupported rich syntax. |

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
the intervention. For later comparison use catalog v1.2 and a new empty world,
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
