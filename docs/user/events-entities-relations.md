# Events, Entities, and Relations

## What this does

Events record what happens and when. Entities represent people, places,
factions, objects, and other things in the world. Relations connect any two
items with a named direction and optional details.

Start with an open world and use the procedures below to create, edit and
connect its entries. See [representations](representations.md) when deciding
between a value, a relation and a prose link. The [time model](temporal-model.md)
explains historical sources; [writing and links](wiki-editor-markdown.md) covers
the exact Markdown vocabulary and Peek.

(help-authoring-create)=

## Create an event or entity

An **Event** records something that happens, such as a coronation or battle. An
**Entity** represents something in your world, such as a person, place or faction.

1. Open the Explorer’s **New** menu.
2. Choose **Create Event** or **Create Entity**.
3. Enter a name and confirm creation. For an Entity, choose its type.
4. Select the new item in the Explorer, add details, then use **Save Changes**
   or wait for the save status to confirm the edit.

Check that the entry remains when you select it again. Cancel a creation
dialog before accepting it if you do not want the entry; use Undo for a saved,
supported creation rather than leaving an unwanted duplicate.

A new Event initially uses the Timeline’s **viewed time**. Check its date in the
inspector, especially when you know only the year or an approximate date. Dates and
durations use the active world calendar.

Creating an item does not automatically connect it to another item. Add a relation when
you want to record a connection.

**Example:** Create “Coronation of Ada” as an Event and “Ada” as an Entity. Then add a
relation to describe Ada’s connection to the coronation.

**Related:** {ref}`Add details <help-authoring-details>` · {ref}`Event dates and
duration <help-event-timing>` · {ref}`Create relations <help-relations-create>`

(help-authoring-details)=

## Add details

Use an item’s inspector to describe it and organize its information. A description holds
narrative text; attributes hold named values; tags help you group and find items.

1. Select an Event or Entity in the Explorer.
2. Edit its name, type or description.
3. Add attributes for details you want to record separately, such as an occupation or population.
4. Add tags, images and captions as needed.
5. Open **Connections** to review or create relations.
6. Choose **Save Changes**, or wait for the separate save status to confirm
   the edit, then reopen the same entry to verify its content.

Descriptions support formatting and `[[Wiki Links]]`. Creating a wiki link does not
replace the deliberate creation of a named relation.

When editing an Entity at a historical time, check **Source** before changing a
description or attribute. Correcting an existing value changes its displayed source; it
does not necessarily create a new dated change.

**Example:** Give Ada a narrative description, an `occupation` attribute and a `royalty`
tag. Add a relation separately to record her membership in a dynasty.

**Related:** {ref}`Writing and links <help-writing-edit>` · {ref}`Historical Entity
editing <help-entity-historical-editing>` · {ref}`Value Source
<help-entity-value-source>` · {ref}`Attributes, relations and mentions
<help-authoring-representations>`

(help-authoring-representations)=

## Attributes, relations, and mentions

Attributes, relations and prose express different kinds of information. They can
describe the same subject without being interchangeable.

- **Attribute:** a named value on an entry, such as occupation, population or affiliation. Writing another entry’s name as a value does not create a connection.
- **Relation:** an explicit connection between entries, with direction, meaning and optional timing. The Graph uses relations to show connections.
- **Mention:** a reference in prose. Plain text does not create a link.
- **Linked mention:** a wiki link that lets you navigate to another entry. With **Auto-Create Relations from Wikilinks** enabled, saving a resolved link also records a `mentions` relation.

A `mentions` relation records a reference. It does not assert membership, ownership,
location or another specific relationship.

**Example:** Ada’s `affiliation` attribute can say “Silver Guild”. A membership relation
can connect Ada to the guild for a particular period. Her biography can also link to the
guild. Each representation serves a different purpose.

Changing the attribute does not update the membership relation, and editing the relation
does not rewrite the biography. Review each independently when you intend them to
describe the same fact. Differences can also be deliberate—for example, a quoted claim
alongside an uncertain connection.

**Related:** {ref}`Create relations <help-relations-create>` · {ref}`Relation timing
<help-relations-timing>` · {ref}`Historical Entity editing
<help-entity-historical-editing>` · {ref}`Wiki links <help-writing-links>`

### Examples

The table is a comparison reference. For the conceptual model, see
[Understand attributes, relations and mentions](representations.md).

| What you want to express | What each representation gives you |
| --- | --- |
| Alice has grey eyes | An **Eye colour** attribute stores **Grey** as a value on Alice's entry. |
| Alice belongs to the Silver Guild | An **Affiliation** attribute can store the guild's name. A **Member of** relation explicitly connects Alice to the guild's entry. You may use either or both, depending on what you want to record. |
| Alice's biography discusses the Silver Guild | Plain prose records the discussion. A linked mention additionally lets you open the guild's entry; it does not by itself record membership. |
| Alice belonged to the guild during a particular period | A membership relation can carry start and end boundaries for connection views. A dated attribute can describe affiliation in Alice's historical record. These express different parts of the model and are edited separately. |
| A source lists Alice's affiliation as "Silver Guild" | An attribute can preserve that source's label even when the guild has no entry. An unresolved WikiLink can preserve a reference in prose while you write. |
| Alice joined the guild at a ceremony | An event can describe the joining, a relation can record membership, and prose can tell the story. You can combine them without one replacing the others. |


(help-event-timing)=

## Set an event date or duration

An Event's start and end each have a date source. **Manual date** records your
date evidence. **Follow Event** calculates a date from another Event's start or
end and an offset. Date uncertainty does not, by itself, imply duration.

Everything in the **Date** frame is saved together with **Save Changes**. You can
adjust the date, time, uncertainty, sources, endpoints, offsets and duration without
autosave opening a timing review partway through. Other fields continue to
autosave separately; that does not save or replace your timing draft. The status
**Timing not saved — choose Save Changes** identifies the remaining draft.

1. Select the Event. Leave its start source as **Manual date** and enter a date
   using the world's calendar. Press **Enter**, or leave the field, to validate it.
2. Use **Date details & uncertainty…** for separate components or uncertain dates.
3. To record an interval, enable **Event has an end** and expand
   **End date / duration…**. Choose **Duration** for a fixed elapsed length, or
   **End Date** for an independently authored end.
4. Choose **Save Changes**. Wait for timing validation to finish. If a cascade
   review appears, inspect the changed Events and affected uses, then choose
   **Apply changes** to save the whole change together.
5. Check the save status and the calculated timing shown in the inspector.

**Duration** keeps the elapsed length when the start changes. **End Date** keeps
the end's own source and recalculates the possible duration. An explicit
zero-day duration has an end that other Events can follow. An occurrence with
**Event has an end** unchecked has no referenceable end.

Validation accepts a date locally; it does not confirm a save. Invalid or
unfinished input is not saved. Press **Escape** in an unaccepted date field to
restore its last accepted value. Cancelling validation or cascade review leaves
your draft available for correction. **Undo** reverses the accepted cascade as
one operation.

### Make one Event follow another

First save the source Event. For example, a fictional siege can end when a
treaty begins; this example does not require changing the demo world.

1. Select the siege, enable **Event has an end**, and choose **End Date**.
2. Change the end's source from **Manual date** to **Follow Event**.
3. Choose the treaty from the Event list. Expand the follow options and choose
   its **Start** or **End** endpoint.
4. Enter an offset. **Days** accepts signed fractional values; calendar months
   and years require whole numbers and use the selected calendar's actual rules.
5. Choose **Save Changes**, review any cascade, and choose **Apply changes**. Reopen the
   Event and check the saved reference and calculated result.

The same controls are available for the start. All four start/end combinations
are supported. A source without an authored end cannot supply an end date.
Self references and endpoint dependency cycles are rejected; use **Duration**
to define an Event's end relative to its own start.

Changing a source recalculates its dependents, including Map and Relation date
windows. Interval ordering and chronology may narrow the feasible dates without
replacing your authored evidence. The saved calculation and reference summary
show the result; **Date details & uncertainty…**, **Date evidence…**, and
**Chronology…** retain the underlying authoring routes. A change with no jointly
possible interpretation cannot be saved. Calendar offsets must work for every
otherwise possible source date; refine the source evidence if a candidate date
has no corresponding day or month.

To detach, choose **Manual date**. An exact result can be copied into the field.
For uncertain timing, enter an explicit replacement date or uncertainty before
saving. A followed start cannot be dragged on the Timeline: edit its offset or
detach it in the inspector. Resolve all timing references before deleting a
source Event or removing its referenced end.

Accepted Timeline moves and Undo/Redo refresh timing that you are not editing,
while keeping your writing draft. A timing draft stays intact if its saved date
changes elsewhere. In that case, saving reports the conflict. **Discard** reloads
the saved Event and replaces its unsaved changes; preserve any draft you need
before discarding, then reapply the intended timing change.

Imported broken references remain editable. A known start with an unresolved
end has no invented duration bar; an entirely unplaced Event remains accessible
in Explorer. Unsupported timing metadata is preserved and its timing controls
are unavailable until it can be repaired safely.

**Related:** {ref}`Date precision <help-date-precision>` · {ref}`Date evidence
<help-date-evidence>` · {ref}`Chronology <help-event-chronology>` · {ref}`Timeline
viewing <help-timeline-viewing>`

(help-control-event-timing)=

> Choose Manual date to author date evidence, or Follow Event to calculate a start or end from another Event. Event has an end distinguishes an interval from an occurrence. Duration fixes elapsed length; End Date gives the end its own source. Date-frame edits wait for Save Changes; autosave saves other fields separately. Save Changes validates the joint timing and asks you to review dependent changes. Cancelling keeps your draft. A followed start cannot be dragged. Detaching uncertain timing requires a replacement date. Resolve references before deleting a source or removing its end.

(help-inspect-event-start-source)=

**Start date source** — Choose Manual date or Follow Event. Changing to Manual
date requires a deliberate replacement when the calculated date is uncertain.

(help-inspect-event-start-reference)=

**Event followed by start** — Select the saved Event supplying this start.
Unavailable imported targets remain visible for repair.

(help-inspect-event-end-source)=

**End date source** — Choose the independent end's Manual date or Follow Event
source. Select End Date first to author an independent end.

(help-inspect-event-timing-review-actions)=

**Review date changes** — Read each affected Event or use, including its Before
and After dates, uncertainty and interval duration. Dates retain their clock time
when one is set; possible ranges retain their boundaries. **Apply changes** saves the
reviewed operation with one Undo. **Cancel** returns to your intact draft.

(help-inspect-event-end-reference)=

**Event followed by end** — Select the saved Event supplying this end. The end
must remain jointly feasible with this Event's start.

(help-inspect-event-follow-options)=

**Follow options** — Expand the source endpoint and offset controls. Opening
these options does not save a timing change.

(help-inspect-event-follow-endpoint)=

**Source endpoint** — Follow the source Event's Start or authored End. An
occurrence without an end cannot supply End; a zero-duration interval can.

(help-inspect-event-follow-offset)=

**Offset** — Add a signed amount to the source endpoint. Negative values place
the calculated date earlier. Fractional values are available for Days.

(help-inspect-event-follow-unit)=

**Offset unit** — Choose Days, Calendar months, or Calendar years. Calendar
units require whole amounts and valid target dates for every possible source.

(help-inspect-event-timing-evidence)=

**Evidence and timing constraints** — Inspect saved authored evidence separately
from feasible dates, including gaps and excluded bounds. Applicable interval,
reference, and chronology rules explain the connected timing group. Opening this
disclosure preserves your draft and does not save changes.

(help-entity-historical-editing)=

## View and correct an entity at another time

An Entity can have baseline values and dated changes. Moving the Timeline playhead shows
the values that apply at the viewed time; it does not automatically turn your next edit
into a new historical change.

1. Select the Entity and move to the time you want to inspect.
2. Check **Source** for the description or attribute you want to edit.
3. Correct an existing value to update its displayed source.
4. When adding an attribute, choose **Entity baseline** or **At this time**. For a dated change, choose an event at the viewed time or create one.

Use **Start a new description at this time** when a description should change from that
point onward, rather than correcting the source currently shown.

When removing a visible dated attribute, distinguish making it absent at this time from
removing its source override. Removing an override can reveal an earlier or baseline
value.

**Example:** Ada’s title changes from “Princess” to “Queen” at her coronation. Record a
dated change for that transition. If the coronation’s title contains a spelling mistake,
correct its existing source instead.

Changing an attribute does not automatically update a similarly named relation or wiki
mention.

**Related:** {ref}`Value Source <help-entity-value-source>` · {ref}`Timeline viewing
<help-timeline-viewing>` · {ref}`Attributes, relations and mentions
<help-authoring-representations>`

(help-control-entity-historical-editing)=

> Entity baseline stores an attribute in the entity's ordinary record. At this time starts a dated change using an event at the viewed time, or an event you create for that change. Choose the destination deliberately when adding an attribute: viewing another year does not make every field a new dated fact. Correcting an existing visible value edits its displayed source instead. Starting a new description at this time creates a dated description change. These operations do not automatically create a membership relation or update a similarly worded linked mention.

(help-entity-value-source)=

## Understand where a visible value comes from

**Source** identifies the baseline or dated event supplying the description or attribute
currently shown in the Entity inspector. Check it before deciding whether to correct a
value or start a new historical change.

1. Select an Entity and move the Timeline to the time you want to inspect.
2. Read the description’s **Source** label or the attribute’s source information.
3. Correct the visible value if that source contains an error.
4. Use a deliberate dated change when the value should become different from a later time onward.

An ordinary correction updates the displayed source. Correcting a dated value keeps the
correction with its event; correcting a baseline value changes the Entity’s baseline.

Source is an explanation of provenance, not a command to copy the visible value into the
baseline. It also does not imply that attributes, relations and wiki mentions have
synchronized.

**Example:** Ada’s title at 970 comes from her coronation event in 962. Correcting
“Quen” to “Queen” updates that dated source. Recording a later abdication requires a new
dated change.

**Related:** {ref}`Historical Entity editing <help-entity-historical-editing>` ·
{ref}`Timeline viewing <help-timeline-viewing>` · {ref}`Attributes, relations and
mentions <help-authoring-representations>`

(help-control-entity-value-source)=

> Source identifies the baseline or dated event supplying the value currently shown in the Entity inspector. It explains which authored source an ordinary correction will change; it is not a command to copy the value into the baseline. Move the playhead to view another time, then check Source before correcting the visible description or attribute. Use a deliberate new dated change when the meaning begins at a later time. A source label does not claim that independent attributes, relations and linked mentions have synchronized.

(help-writing-focus)=

## Focus on writing

Focus writing gives the selected Event or Entity’s description a centered writing
surface while dimming the surrounding workspace.

1. Select an Event or Entity.
2. Choose **Focus writing** in the description toolbar, or press **F11**.
3. Continue editing. Use **Formatting** and **Contents** when you need those tools.
4. Choose **Exit focus**, or press **F11** again, to return to the inspector.

You are editing the same description, not a separate copy. Leaving Focus writing
preserves your text, caret, selection and scroll position, and restores the normal
inspector layout.

Links remain available while you write. You can also press **F1** for Help. Returning
from Help keeps Focus writing active; closing Help does not exit the writing surface.

**Example:** Open Ada’s biography in Focus writing to revise several paragraphs. Return
to the inspector when you want to work on her attributes or connections.

**Related:** {ref}`Rich and Source writing <help-writing-edit>` · {ref}`Wiki links
<help-writing-links>` · {ref}`Add details <help-authoring-details>`

(help-relations-create)=

## Create relations

Relations record named, directional connections between Events and Entities. Use them
when you want to express something beyond a value or a reference in prose.

1. Select an Event or Entity and open **Connections**.
2. Choose **Connect…**, then choose an existing target.
3. Review the connection and select **Connect** to save, or **Cancel** to discard.
4. Single-click a saved relation to select it. Choose **Edit**, press Enter while
   the overview has focus, or double-click the row to refine its meaning and details.

Connections appear in groups based on their recorded meaning, for both incoming
and outgoing relations. Unknown meanings appear under **Other connections**.
System-managed mentions appear under **References** and cannot be edited here.
Expand a group to browse it; its count describes the rows matching your filters.

Use **Find a connection…** to search entry names and relationship wording.
**Filters** limits direction or groups and can hide References. A hidden selection
remains identified in the selection summary; filtering never chooses another row.

The overview stays above the **Edit relationship** panel, whose assertion is a
plain heading. Drag the divider to adjust their space. **Cancel** discards only
the local draft. Selecting another relationship with unfinished changes
offers **Apply / Discard / Keep editing**. After Apply, wait for the save result
before selecting again. Notes keep multiline Enter behavior.

**Meaning** is an editable dropdown: choose an existing suggestion or type a new
relationship phrase directly. A selected suggestion reuses its existing type;
opening a readable caption or changing Notes does not rename its stored type.
There is no separate Custom type field. Navigation and removal are under the
overview's visible **More actions** menu; **Edit** stays beside the selection.

You can also drop an existing Event or Entity onto the labeled connection target. In
this workflow, the **dropped entry is the source** and the **inspected entry is the
target**. Review that direction before connecting. Dropping elsewhere in the inspector
does not create a relation.

For advanced options, use **More actions → Add detailed
relation…** or **Full relation editor…**.

(help-connections-connect)=

**Connect…** prepares a connection to an existing entry. Choosing a target does
not save it: review the direction, then use Connect or Cancel. Event participant
and location presets are also available under More actions.

(help-connections-search)=

**Find a connection…** searches connected names, displayed meanings and stored
relationship types. It changes only the overview. Hidden selections retain their
identity and any open draft; clear the search to reveal them again.

(help-connections-filters)=

**Filters** shows incoming and outgoing assertions, semantic groups and the
References inclusion choice. These presentation choices never rewrite relations.
References are included by default in a collapsed, read-only group.

(help-connections-overview)=

**Connections overview** lists each saved relation once by its identity. Read
the source, meaning and target together to understand its direction. Timing and
state-change information belong to that same assertion. Single-click selects;
Edit, Enter or double-click opens its editor. Expand headings to browse groups.
Each relation appears on one line. Long rows shorten with an ellipsis; hover over
the row to read the full assertion, including its direction and timing.

(help-connections-edit)=

**Edit** opens the selected authored relationship below the overview. Apply
updates that same saved relation; Cancel discards only the local draft. Unfinished
changes are guarded before choosing another relationship. References are read-only.

(help-connections-navigate)=

**Go to connected entry** requests navigation to the opposite endpoint of the
selected assertion. Navigation respects unfinished drafts. It does not create an
inverse relationship, change the viewed time or apply the current edit silently.

(help-connections-remove)=

**Remove** requests deletion of the selected authored relationship after the
draft guard and confirmation. It does not delete either endpoint. System-managed
References cannot be removed here; change their originating prose instead.

A relation does not automatically change a similarly named attribute or wiki link.
Creating a reverse connection is a separate deliberate choice.

**Example:** Record Ada’s membership in a dynasty as a relation. Read the source, target
and meaning together to ensure the connection expresses the intended direction.

**Related:** {ref}`Relation timing <help-relations-timing>` · {ref}`Attributes,
relations and mentions <help-authoring-representations>` · {ref}`Wiki links
<help-writing-links>`

(help-control-relations-create)=

> Direction identifies the source and target of a connection. Read the relation preview before saving: the subject and target determine how the relation is understood. In the inspector drop workflow, the dropped entry is the source and the inspected entry is the target. Creating a reverse link is a separate deliberate choice, rather than an automatic consequence of every connection. Changing direction does not synchronize a similarly named attribute or wiki mention. Inspecting the control only explains this choice; it does not connect entries, reverse a relation or save a draft.

(help-relations-timing)=

## Historical validity and uncertainty

Relation timing records when a connection applies, including boundaries whose exact
dates are unknown.

1. Open the relation for refinement.
2. Choose its **Meaning**:
   - **Active state:** follows its validity boundaries.
   - **Historical fact:** remains available after it happens.
   - **Occurrence:** appears in history views.
   - **Timeless association:** does not depend on the playhead.
3. Open **Timing…** to configure the start and end boundaries. Choose a manual date, a named event, **Date not known**, or **Unbounded** for each boundary.
4. Review and apply the changes.

**Date not known** means the boundary is unresolved. **Unbounded** means there is no
limit on that side. The end boundary is exclusive: the relation no longer holds at its
end transition.

When two roles share a handover, bind the outgoing role’s end and the successor’s start
to the same Event. This preserves their shared transition even if its calendar date is
uncertain. Copying the Event’s displayed position into two manual dates does not
preserve that identity.

**Example:** Ada succeeds Borin at a coronation known only to 962. Bind Borin’s role end
and Ada’s role start to that coronation Event, rather than inventing an exact day.

Named Event boundaries share the same **Endpoint and offset…** controls as
{ref}`map visibility dates <help-map-visibility>`. Choose **Occurrence / start**
or **Authored end**; a missing authored end remains unresolved. Signed offsets
support fractional lore days or whole calendar months/years. Invalid target
dates remain unresolved, including coarse occurrence dates with any invalid
possible target.

**At event endpoint** shares a transition. **Date before endpoint** and **Date
after endpoint** describe independently unknown dates strictly before/after the
shifted endpoint; they are not visibility switches at that Event. Existing
relative-date records retain their saved semantics until explicitly edited.
An equal start/end state interval is empty, not an occurrence: choose
**Occurrence** deliberately when that is the intended meaning.

**Related:** {ref}`Chronology <help-event-chronology>` · {ref}`Date precision
<help-date-precision>` · {ref}`Create relations <help-relations-create>` ·
{ref}`Timeline viewing <help-timeline-viewing>`

(help-control-relations-timing)=

> Meaning distinguishes an active state, a historical fact, an occurrence and a timeless association. Start and end boundaries can use manual dates, named events, unknown dates or unbounded sides. Unknown means unresolved; unbounded means no limit on that side. The end transition is exclusive. Bind an outgoing role's end and a successor's start to the same event to record a shared handover, even when its exact date is uncertain. Copying an event's displayed timeline coordinate into two manual dates does not preserve that shared-event identity.

### Read relation timing in the Graph

**Meaning** distinguishes an active state, an enduring historical fact, an
occurrence, and a timeless association. The Graph offers:

- **At playhead**: current states and established historical facts. Occurrence
  edges are reserved for history views.
- **History to playhead**: includes ended states and occurrences, excluding
  relations known to begin in the future.
- **All relations**: retains the full relationship history with timing labels.

The uncertainty count remains visible when possible relations are hidden.
Use **Show possible relations**, or select a node to reveal its possible
connections. Dashes and `(?)` identify uncertain edges without relying on
color. Moving the playhead preserves graph positions, zoom, and selection
when the node set stays the same.

Entity state applies only changes established at the playhead. The inspector
lists possible changes separately instead of choosing an arbitrary winner.
Map layers similarly mark uncertain presence with `(?)` and reduced opacity;
their associated routes follow the layer's visibility.

## Wiki links

Type `[[` in a description to search for an event or entity. Select a
suggestion to insert the link. Hold **Ctrl** and click a link to navigate to its
target.

**Settings → Auto-Create Relations from Wikilinks** controls whether saving a
wiki link also creates a `mentions` relation.

## Common workflow: build a character

1. Create an entity and choose an appropriate type.
2. Add the character's description and tags.
3. Attach a portrait.
4. Create relations to factions, locations, and other characters.
5. Create dated events for important moments in the character's history.
6. Use the Graph and Timeline to review the resulting context.

Save the description and other edited fields before treating this workflow as
complete. Reopen the character to check its content and review relation
direction separately. For a guided introduction with prepared checkpoints,
use the [Northwatch tutorial](northwatch-tutorial.md).

(help-authoring-delete)=

## Delete an entry deliberately

1. Select the intended entry in Project and choose **Delete**.
2. Check the name and any dependency warnings in the confirmation.
3. Confirm only if you intend to remove the entry from the world. Choose
   **Cancel** to keep it.

Check that the entry has disappeared from Project. This is different from
removing an entry from one Longform document. Supported world-entry deletions
can be undone; deleting or restoring a complete world is a separate operation.

(help-media-gallery)=

## Manage images and captions

The gallery attaches images and captions to the selected entry. Add imports an image;
editing changes its gallery details; removing an attachment removes that gallery item.
Review confirmation before removal and keep a portable world package when assets must
travel with the world.

(help-authoring-tags)=

## Organize entries with tags

Tags group entries for filtering and discovery. Add or remove a tag deliberately;
changing a tag does not create a relation. Context-tag controls manage which tags are
suggested or used in the current authoring context.

(help-authoring-templates)=

## Insert structured content with Fast Inject

Fast Inject applies a selected structured template to an entry. Review the source and
overwrite choice before applying: accepting can change fields, while cancelling leaves
the entry unchanged. Saving a template source changes the reusable template rather than
applying it to the entry.

## Interface control reference

These explanations describe the software operation. Inspecting a control does not run it or read your entered values.

(help-inspect-src-gui-dialogs-context-tag-dialogs-contexttageditordialog-init-self-btn-cancel)=

**Cancel** — Cancel this ContextTagEditor operation without accepting its pending
changes. This is separate from applying or saving them.

(help-inspect-src-gui-dialogs-context-tag-dialogs-contexttageditordialog-init-self-btn-save)=

**Save** — Accept the current ContextTagEditor choices after validation. Review the
fields first; opening Help does not accept them.

(help-inspect-src-gui-dialogs-context-tag-dialogs-contexttageditordialog-init-self-btn-primary)=

**Accept context tags** — Accept the selected context tags for this authoring context.
This does not create a relation.

(help-inspect-src-gui-dialogs-context-tag-dialogs-contexttagreviewdialog-init-self-btn-all)=

**Select All** — Select all available choices in this list. This changes the local
selection; use the surrounding Apply or Save action to accept it.

(help-inspect-src-gui-dialogs-context-tag-dialogs-contexttagreviewdialog-init-self-btn-none)=

**Select None** — Clear the local selection without deleting the listed items.

(help-inspect-src-gui-dialogs-context-tag-dialogs-contexttagreviewdialog-init-self-btn-clear)=

**Clear Review History** — Clear the context-tag review history. This is separate from
deleting world entries or removing tags from every entry.

(help-inspect-src-gui-dialogs-context-tag-dialogs-contexttagreviewdialog-init-self-btn-close)=

**Close review** — Close the context-tag review dialog.

(help-inspect-src-gui-dialogs-context-tag-dialogs-contexttagreviewdialog-init-self-btn-cleanup)=

**Remove context tags** — Remove the selected context-tag assignments through the review
workflow. This is separate from deleting the tagged entries.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-self-name-edit)=

**Template name** — Name the reusable entry template being created from the current
selection.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-self-desc-edit)=

**Template description** — Describe when this entry template should be used.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-btn-all)=

**Select All** — Select all available choices in this list. This changes the local
selection; use the surrounding Apply or Save action to accept it.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-btn-none)=

**Select None** — Clear the local selection without deleting the listed items.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-chk)=

**Include field** — Include this field in the entry template. Unchecked fields are
omitted from the saved template.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-self-chk-type)=

**Include type** — Include the selected entry's type in the template.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-btn-all-a)=

**Select All** — Select all available choices in this list. This changes the local
selection; use the surrounding Apply or Save action to accept it.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-btn-none-a)=

**Select None** — Clear the local selection without deleting the listed items.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-chk-2)=

**Include attribute** — Include this attribute in the entry template. Unchecked
attributes are omitted.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-self-chk-layout)=

**Include visual sheet layout** — Include the selected entry's visual sheet arrangement
in the template, alongside the chosen fields.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-btn-cancel)=

**Cancel** — Cancel this CreateTemplate operation without accepting its pending changes.
This is separate from applying or saving them.

(help-inspect-src-gui-dialogs-create-template-dialog-createtemplatedialog-setup-ui-btn-save)=

**Save entry template** — Save the selected fields as a reusable template. This does not
apply the template to another entry.

(help-inspect-src-gui-dialogs-entity-creation-dialog-entitycreationdialog-init-self-name-edit)=

**Entity name** — Name the new Entity. The name can be edited later; it does not itself
create connections.

(help-inspect-src-gui-dialogs-entity-creation-dialog-entitycreationdialog-init-self-type-combo)=

**Entity type** — Choose or enter a type for the new Entity, such as character or
location.

(help-inspect-src-gui-dialogs-entity-creation-dialog-entitycreationdialog-init-self-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-setup-ui-self-list-widget)=

**Entry templates** — Select a template to configure its included fields and proposed
values before applying it to the inspected entry.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-setup-ui-self-btn-import)=

**Import template** — Choose a template file to make available in the Inject dialog.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-setup-ui-self-btn-cancel)=

**Cancel** — Cancel this FastInject operation without accepting its pending changes.
This is separate from applying or saving them.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-setup-ui-self-btn-apply)=

**Apply template** — Apply the selected template and enabled fields to the current
entry. Review the overwrite choice first.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-setup-configure-tab-self-chk-overwrite)=

**Overwrite existing values** — Allow included template fields to replace values already
present on the entry. Leave unchecked to protect existing keys.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-setup-source-tab-self-txt-source)=

**Template source** — Edit the selected template's source. Save Changes writes the
template; Apply Template is a separate action on the current entry.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-setup-source-tab-self-btn-save-source)=

**Save template changes** — Save the edited template source without applying it to the
inspected entry.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-add-row-chk)=

**Include template field** — Include this field when applying the template. Unchecked
fields are left out.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-add-row-input-widget)=

**Template field value** — Choose the proposed value for this included template field
before applying it.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-add-row-input-widget-2)=

**Template field value** — Edit the proposed text for this included template field
before applying it.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-add-row-input-widget-3)=

**Template field value** — Edit the proposed text for this included template field
before applying it.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-add-row-input-widget-4)=

**Template field value** — Edit the proposed text for this included template field
before applying it.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-add-row-sub-inp)=

**Template detail value** — Choose the proposed value for this template detail before
applying it.

(help-inspect-src-gui-dialogs-fast-inject-dialog-fastinjectdialog-add-row-sub-inp-2)=

**Template detail value** — Edit the proposed value for this template detail before
applying it.

(help-inspect-src-gui-dialogs-image-viewer-dialog-imageviewerdialog-init-ui-self-btn-prev)=

**&lt; Previous** — Show the previous available item in this viewer without deleting or
editing the current item.

(help-inspect-src-gui-dialogs-image-viewer-dialog-imageviewerdialog-init-ui-self-btn-next)=

**Next image** — Show the next image in this gallery viewer without editing the image or
caption.

(help-inspect-src-gui-dialogs-relation-dialog-relationeditdialog-init-self-button-box)=

**Button box** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-widgets-attribute-editor-attributeeditorwidget-init-self-btn-add)=

**Add attribute** — Add an attribute row to the current entry draft. Historical editing
asks where a new value belongs.

(help-inspect-src-gui-widgets-attribute-editor-attributeeditorwidget-init-self-btn-remove)=

**Remove attribute** — Remove the selected attribute from the draft. Historical editing
distinguishes dated absence from removing a source override when saved.

(help-inspect-src-gui-widgets-attribute-editor-attributeeditorwidget-init-self-table)=

**Entry attributes** — Edit attribute keys, values and types. The Source column
identifies where a historical value comes from.

(help-inspect-src-gui-widgets-attribute-editor-attributeeditorwidget-add-row-combo)=

**Attribute type** — Choose how this attribute value is interpreted, such as text,
number or true/false.

(help-inspect-src-gui-widgets-compact-duration-widget-compactdurationwidget-setup-ui-self-spin-years)=

**Duration years** — Set the year component of the elapsed duration using the active
calendar.

(help-inspect-src-gui-widgets-compact-duration-widget-compactdurationwidget-setup-ui-self-spin-months)=

**Duration months** — Set the month component of the elapsed duration using the active
calendar.

(help-inspect-src-gui-widgets-compact-duration-widget-compactdurationwidget-setup-ui-self-spin-days)=

**Duration days** — Set the day component of the elapsed duration.

(help-inspect-src-gui-widgets-compact-duration-widget-compactdurationwidget-setup-ui-self-spin-hours)=

**Duration hours** — Set the hour component of the elapsed duration.

(help-inspect-src-gui-widgets-compact-duration-widget-compactdurationwidget-setup-ui-self-spin-minutes)=

**Duration minutes** — Set the minute component of the elapsed duration.

(help-inspect-src-gui-widgets-context-tag-bar-contexttagbar-init-self-btn-review)=

**Review** — Review context-tag suggestions before accepting or dismissing them.
Reviewing does not automatically add the suggestions as authored content.

(help-inspect-src-gui-widgets-context-tag-bar-contexttagbar-init-self-btn-enable)=

**Enable** — Enable this context-tag behavior. Review the active tags; this is separate
from creating a relation.

(help-inspect-src-gui-widgets-context-tag-bar-contexttagbar-init-self-btn-edit)=

**Set context tags** — Choose the tags used by this authoring context. This is separate
from creating a connection.

(help-inspect-src-gui-widgets-context-tag-bar-contexttagbar-init-self-btn-disable)=

**Disable** — Disable this context-tag behavior without deleting the underlying world
entries.

(help-inspect-src-gui-widgets-editor-presentation-editorpresentation-install-focus-button-self-focus-button)=

**Focus button** — Enter or leave the focused writing presentation while retaining the
same live description, caret and scroll position.

(help-inspect-src-gui-widgets-editor-presentation-editorpresentation-install-toolbar-menus-button)=

**Inspector menu** — Open the inspector's secondary actions without applying one.
Inspect individual menu items for their effects.

(help-inspect-src-gui-widgets-editor-presentation-editorpresentation-install-toolbar-menus-menu)=

**Inspector actions** — Choose an additional inspector operation. Inspection explains
the item without running it.


(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-details-tab-self-desc-edit)=

**Entity description** — Edit the Entity description at the displayed source. To begin a
new dated description, use Start a new description at this time.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-details-tab-self-description-field)=

**Entity description** — Edit the Entity description at the displayed source. This is
separate from the summary and linked-entry mentions.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-details-tab-self-btn-new-description)=

**Start a new description at this time** — Start a new dated description change at the
viewed time, rather than correcting the source currently displayed.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-timeline-section-self-timeline-checkbox)=

**Timeline** — Show or hide the selected Entity’s linked-event Timeline section. This
changes section visibility without deleting events.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-summary-section-self-summary-checkbox)=

**Summary** — Show or hide the summary section for the selected entry. Hiding the
section does not delete its saved summary.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-llm-section-self-llm-checkbox)=

**Generation section** — Show or hide the description-generation controls. Opening the
section does not request generated text.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-raster-appearances-section-self-raster-appearances-checkbox)=

**Raster maps** — Show or hide the selected entry’s raster-map appearances section. This
does not edit raster data.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-header-self-btn-inject)=

**Inject** — Quickly apply templates or snippets to this entity.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-header-self-inject-menu)=

**Inject actions** — Choose a reusable entry template or open the Inject dialog to
review its fields.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-header-self-name-edit)=

**Entity name** — Edit this Entity's name. Its identity and existing connections are
retained.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-header-self-type-edit)=

**Entity type** — Edit this Entity's type. The type helps categorize entries; it is
separate from tags and relations.





(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-action-buttons-self-btn-save)=

**Save Changes** — Save the inspector’s current changes. For historical values,
corrections go to their displayed source; check the save status for confirmation.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-action-buttons-self-btn-discard)=

**Discard** — Discard unsaved inspector changes and return to the saved content. Discard
is deliberate and is different from hiding the inspector.




(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-new-attribute-destination-baseline)=

**Entity baseline** — Store the new attribute in the Entity’s ordinary baseline. A dated
absence can still hide it at the viewed time; review the warning before accepting.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-new-attribute-destination-dated)=

**At this time** — Start a dated attribute change using an event at the viewed time.
This is different from changing the Entity baseline.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-save-temporal-absent)=

**Absent from this state** — Record that this attribute is absent at this historical
state. This does not mean revealing an earlier value.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-save-temporal-override)=

**Remove source override** — Remove this attribute's current override so an earlier or
baseline value can become visible. This differs from recording dated absence.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-populate-inject-menu-action-dialog)=

**Open Inject dialog** — Review a reusable entry template and its proposed fields before
applying it to this Entity.

(help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-populate-inject-menu-action-save-tmpl)=

**Save entry template** — Create a reusable template from selected fields of this
Entity. This does not duplicate the Entity itself.

(help-inspect-src-gui-widgets-entity-list-entitylistwidget-init-self-btn-create)=

**New Entity** — Create an Entity, such as a character, location or faction. Connections
and map placement are separate actions.

(help-inspect-src-gui-widgets-entity-list-entitylistwidget-init-self-btn-delete)=

**Delete Entity** — Delete the selected Entity from the world after confirmation. Review
dependent connections and raster references.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-desc-edit)=

**Event description** — Edit this Event's description. Description text is separate from
its date, duration and chronology constraints.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-description-field)=

**Event description** — Edit this Event's description. Wiki links can mention entries
without asserting an authored relationship.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-summary-section-self-summary-checkbox)=

**Summary** — Show or hide the summary section for the selected Event without deleting
its saved summary.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-llm-section-self-llm-checkbox)=

**Generation section** — Show or hide description-generation controls. Opening the
section does not request generated text.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-raster-appearances-section-self-raster-appearances-checkbox)=

**Raster maps** — Show or hide the Event’s raster-map appearances section without
editing the raster data.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-header-self-btn-inject)=

**Inject** — Quickly apply templates or snippets to this event.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-header-self-inject-menu)=

**Inject actions** — Choose a reusable entry template or open the Inject dialog to
review its fields.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-header-self-name-edit)=

**Event name** — Edit this Event's name. Renaming does not change its date or
connections.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-header-self-type-edit)=

**Event type** — Edit the Event's category. Its type is separate from tags and relation
meanings.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-action-buttons-self-btn-save)=

**Save Changes** — Save the Event’s current changes. Invalid or incomplete dates must be
corrected before they can be saved; check the save status for confirmation.
Everything in the Date frame requires this explicit save. Autosaving other fields
keeps the timing draft available for further editing.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-action-buttons-self-btn-discard)=

**Discard** — Discard unsaved Event changes and return to the saved content. This
includes unfinished inspector edits.





(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-populate-inject-menu-action-dialog)=

**Open Inject dialog** — Review a reusable entry template before applying its selected
fields to this Event.

(help-inspect-src-gui-widgets-event-editor-eventeditorwidget-populate-inject-menu-action-save-tmpl)=

**Save entry template** — Create a reusable template from selected Event fields. This
does not create another Event.




(help-inspect-src-gui-widgets-event-list-eventlistwidget-init-self-btn-delete)=

**Delete Event** — Delete the selected Event from the world after confirmation. Review
affected connections before accepting. Timing references block deletion until you
replace or remove them; confirmation cannot leave those references broken.

(help-inspect-src-gui-widgets-gallery-widget-gallerywidget-init-ui-self-btn-add)=

**Add gallery image** — Choose an image to attach to this entry's gallery.

(help-inspect-src-gui-widgets-gallery-widget-gallerywidget-init-ui-self-btn-edit)=

**Edit image caption** — Edit the caption associated with the selected gallery image.

(help-inspect-src-gui-widgets-gallery-widget-gallerywidget-init-ui-self-btn-remove)=

**Remove gallery image** — Remove the selected gallery attachment from this entry after
confirmation.

(help-inspect-src-gui-widgets-gallery-widget-gallerywidget-init-ui-self-list-widget)=

**Gallery images** — Browse images attached to this entry. Open an image to view it at a
larger size.

(help-inspect-src-gui-widgets-gallery-widget-gallerywidget-show-context-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-gallery-widget-gallerywidget-show-context-menu-view-action)=

**View image** — Open the selected gallery image in the image viewer.

(help-inspect-src-gui-widgets-gallery-widget-gallerywidget-show-context-menu-edit-caption-action)=

**Edit image caption** — Edit the selected image's gallery caption without replacing the
image.

(help-inspect-src-gui-widgets-gallery-widget-gallerywidget-show-context-menu-remove-action)=

**Remove gallery image** — Remove this gallery attachment from the entry after
confirmation.

(help-inspect-src-gui-widgets-graph-view-graph-widget-graphwidget-setup-ui-self-temporal-mode)=

**Temporal mode** — Choose At playhead, History to playhead or All relations. This
changes the Graph view, not the saved relation meanings or boundaries.

(help-inspect-src-gui-widgets-graph-view-graph-widget-graphwidget-setup-ui-self-show-possible)=

**Show possible relations** — Show or hide relations whose presence at the viewed time
is possible but not established. Saved relation data is unchanged.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-init-menu-button)=

**Menu button** — Open the Menu button menu to choose a related operation. Opening the
menu does not apply any of its actions.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-init-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-init-addaction)=

**Add detailed relation** — Open the detailed creation workflow to choose the target,
relation type and timing before accepting.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-init-addaction-2)=

**Full relation editor** — Open the full editor for the selected relation or creation
workflow, including advanced timing and details.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-stage-drop-meaning)=

**Connection type** — Choose the authored connection type for this proposed link. It is
separate from the connection's temporal meaning.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-progressive-form-self-meaning)=

**Meaning** — Choose an existing authored connection type, such as membership,
or type a new relationship phrase in this same dropdown. Selecting a suggestion
reuses its stored type; merely displaying its readable caption does not rename
that type. Temporal meaning and boundary dates are configured separately.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-progressive-form-self-reverse-button)=

**Reverse direction** — Reverse the proposed connection’s direction. Source-event timing
and state-change constraints can prevent reversal.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-progressive-form-self-timing-disclosure)=

**Timing…** — Expand the connection’s timing controls to review its boundaries and event
bindings. Opening the section does not apply changes.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-progressive-form-self-advanced-disclosure)=

**Advanced disclosure** — Expand advanced connection options, including timing meaning
and custom details. Apply remains a deliberate separate action.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-actions-self-apply-button)=

**Apply button** — Submit the prepared connection or refinement. Review the source,
target and meaning first; changes wait for the save result.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-actions-cancel)=

**Cancel** — Cancel this Connections operation without accepting its pending changes.
This is separate from applying or saving them.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-prepare-to-leave-apply)=

**Apply connection draft** — Save the pending connection draft before continuing the
requested navigation.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-prepare-to-leave-keep)=

**Keep editing connection** — Stay with the unfinished connection draft and cancel the
requested navigation.

(help-inspect-src-gui-widgets-relation-authoring-relationauthoring-prepare-to-leave-discard)=

**Discard connection draft** — Discard the unsaved connection draft and continue the
requested navigation. Saved relations are retained.

(help-inspect-src-gui-widgets-relation-form-relationform-init-self-type-edit)=

**Relation type** — Choose or enter the authored connection type. This is independent of
temporal meaning and boundary dates.

(help-inspect-src-gui-widgets-relation-form-relationform-init-self-weight-spin)=

**Relation weight** — Set the numeric weight recorded on this relation. Weight is
separate from confidence and temporal validity.

(help-inspect-src-gui-widgets-relation-form-relationform-init-self-confidence-spin)=

**Confidence:** — Record confidence for this relation. Confidence describes the authored
connection; it does not establish an exact historical date.

(help-inspect-src-gui-widgets-relation-form-relationform-init-self-notes-edit)=

**Relation notes** — Record notes about this connection without changing either
connected entry's description.

(help-inspect-src-gui-widgets-relation-form-relationform-init-self-rb-absolute)=

**Manual boundaries** — Enter the relation's boundary dates directly instead of binding
them to the source Event.

(help-inspect-src-gui-widgets-relation-form-relationform-init-self-rb-starts)=

**Starts at Event** — Bind the relation's start to the source Event's transition,
preserving shared Event uncertainty.

(help-inspect-src-gui-widgets-relation-form-relationform-init-self-rb-ends)=

**Ends at Event** — Bind the relation's end to the source Event's transition rather than
copying an independent date.

(help-inspect-src-gui-widgets-relation-form-relationform-init-self-rb-at-event)=

**At Event** — Bind both boundaries to the source Event for an occurrence at its
transition.

(help-inspect-src-gui-widgets-relation-form-relationform-init-self-check-from)=

**Start boundary enabled** — Enable a start boundary for this relation. Its boundary
mode determines how its date or Event binding is interpreted.

(help-inspect-src-gui-widgets-relation-form-relationform-init-self-check-to)=

**End boundary enabled** — Enable an end boundary for this relation. Its boundary mode
determines when it stops applying.

(help-inspect-src-gui-widgets-relation-form-relationform-init-self-bi-check)=

**Bidirectional (Create reverse link)** — Also create a reverse connection when
accepting this new relation. This is a deliberate choice, not automatic synchronization.

(help-inspect-src-gui-widgets-relation-form-relationform-group-boundaries-disclosure)=

**Endpoint and offset…** — Expand the Event endpoint and relative-date options,
including signed lore-day or whole calendar-month/year offsets. Collapsing
these controls preserves their values.

(help-inspect-src-gui-widgets-relation-form-relationform-setup-now-actions-self-starts-now-button)=

**Use viewed date for start** — Copy the current viewed date into the relation's start
draft. This does not change World current time.

(help-inspect-src-gui-widgets-relation-form-relationform-setup-now-actions-self-ends-now-button)=

**Use viewed date for end** — Copy the current viewed date into the relation's end
draft. This does not change World current time.

(help-inspect-src-gui-widgets-relation-form-relationform-setup-state-changes-self-unset-attributes-list)=

**Absent attributes** — List attributes to mark absent in the Entity state produced by
this Event relation. This differs from clearing an override to reveal an older value.

(help-inspect-src-gui-widgets-relation-form-relationform-setup-state-changes-self-btn-add-unset)=

**Add absent attribute** — Add an attribute key to mark absent in the dated Entity state
produced by this relation.

(help-inspect-src-gui-widgets-relation-form-relationform-setup-state-changes-self-btn-remove-unset)=

**Remove absence instruction** — Remove the selected key from this relation's absence
instructions. This does not directly delete an Entity attribute.

(help-inspect-src-gui-widgets-relation-form-relationform-setup-state-changes-self-change-description-check)=

**Change state description** — Include a new Entity description in the state change
produced by this Event relation.

(help-inspect-src-gui-widgets-relation-form-relationform-setup-state-changes-self-state-description-edit)=

**Dated state description** — Write the Entity description supplied by this state-
changing Event relation. This is separate from notes about the relation.

(help-inspect-src-gui-widgets-relation-form-relationform-setup-boundary-choices-self-temporal-behavior)=

**Meaning** — Choose whether the connection is an active state, historical fact,
occurrence or timeless association. Meaning affects how historical views interpret its
dates.

(help-inspect-src-gui-widgets-relation-form-relationform-setup-boundary-choices-choice)=

**Boundary mode** — Choose an open boundary, a manual date or a source-Event binding for
this side of the relation.

(help-inspect-src-gui-widgets-relation-form-relationform-setup-boundary-choices-relative)=

**Event-relative boundary** — At the endpoint shares its transition. Before/after
records an independently unknown date strictly before/after the selected endpoint
plus offset. Separate constrained dates do not imply a shared transition.

(help-inspect-src-gui-widgets-relation-form-relationform-setup-boundary-choices-offset)=

**Offset** — Shift the selected endpoint by a signed number of lore days,
calendar months or calendar years. Zero shares the original transition. Calendar
offsets require whole numbers; invalid targets remain unresolved.

(help-inspect-event-anchor-endpoint)=

**Event endpoint** — Follow occurrence/start or the authored end. An independent
end date takes precedence over duration. Without either, an end reference stays
unresolved rather than following the start.

(help-inspect-event-anchor-unit)=

**Offset unit** — Lore days have a fixed length and can be fractional. Calendar
months and years follow the bound calendar's actual lengths and require whole
numbers. Missing target dates and unsupported precision remain unresolved.

(help-inspect-src-gui-widgets-relation-item-widget-relationitemwidget-setup-ui-self-btn-go-to)=

**Open connected entry** — Navigate deliberately to the connected entry in its
inspector. Existing unfinished-work safeguards still apply.

(help-inspect-src-gui-widgets-relation-type-picker-relationtypepicker-setup-ui-self-combo-box)=

**Relation type** — Choose or enter the type to use for this connection.

(help-inspect-src-gui-widgets-relation-type-picker-relationtypepicker-setup-ui-self-ok-button)=

**OK** — Accept the current Relation Type Picker choices after validation. Review the
fields first; opening Help does not accept them.

(help-inspect-src-gui-widgets-relation-type-picker-relationtypepicker-setup-ui-self-cancel-button)=

**Cancel** — Cancel this Relation Type Picker operation without accepting its pending
changes. This is separate from applying or saving them.

(help-inspect-src-gui-widgets-sheet-builder-attributepairwidget-init-self-value-edit)=

**Attribute value** — Edit this sheet attribute's value. Its type determines how the
value is interpreted.

(help-inspect-src-gui-widgets-sheet-builder-attributepairwidget-init-self-type-combo)=

**Attribute type** — Choose the value type for this sheet attribute, such as text,
number or true/false.

(help-inspect-src-gui-widgets-sheet-builder-textblockwidget-init-self-text-edit)=

**Sheet text block** — Edit this free-text block in the visual sheet. It is separate
from the entry's main description.

(help-inspect-src-gui-widgets-sheet-builder-headerwidget-init-self-text-edit)=

**Sheet heading** — Edit this heading in the visual sheet layout.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-init-self-act-add-row)=

**Add sheet attribute** — Add an attribute row to the visual sheet.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-init-self-act-add-spacer)=

**Add Spacer** — Add a spacer to the last row.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-init-self-act-add-divider)=

**Add divider** — Insert a visual divider into the sheet layout.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-init-self-act-add-text)=

**Add text block** — Insert a free-text block into the sheet layout.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-init-self-act-add-header)=

**Add heading** — Insert a heading block into the sheet layout.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-show-context-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-row-context-menu-act)=

**Insert row above** — Insert a new sheet row above the current row.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-row-context-menu-act-2)=

**Insert row below** — Insert a new sheet row below the current row.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-row-context-menu-act-3)=

**Add row spacer** — Add empty layout space to this sheet row.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-row-context-menu-act-4)=

**Remove row spacers** — Remove empty spacer blocks from this sheet row while retaining
its content blocks.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-row-context-menu-act-5)=

**Sheet block width** — Set this block's relative width within its sheet row. This
changes layout rather than the attribute value.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-row-context-menu-act-6)=

**Change attribute type** — Cycle this sheet attribute's value type. Review the existing
value when changing how it is interpreted.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-row-context-menu-act-7)=

**Delete sheet row** — Remove this row and its blocks from the sheet. Review its
contents before deleting it.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-row-context-menu-act-8)=

**Add divider** — Insert a divider into this sheet layout.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-row-context-menu-act-9)=

**Add text block** — Insert a free-text block into this sheet layout.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-row-context-menu-act-10)=

**Add heading** — Insert a heading block into this sheet layout.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-empty-context-menu-act)=

**Add sheet attribute** — Add an attribute to the visual sheet.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-empty-context-menu-act-2)=

**Add divider** — Insert a divider into the visual sheet.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-empty-context-menu-act-3)=

**Add text block** — Insert a free-text block into the visual sheet.

(help-inspect-src-gui-widgets-sheet-builder-sheetbuilderwidget-build-empty-context-menu-act-4)=

**Add heading** — Insert a heading block into the visual sheet.

(help-inspect-src-gui-widgets-tag-editor-tageditorwidget-init-self-tag-input)=

**Tag input** — Type a tag and press Enter….

(help-inspect-src-gui-widgets-tag-editor-tageditorwidget-init-self-btn-add)=

**Add tag** — Add the entered tag to this entry. Tags organize entries without creating
authored connections.

(help-inspect-src-gui-widgets-temporal-range-widget-temporalrangewidget-setup-ui-self-has-duration)=

**Event has an end** — Enable an authored end, including an explicit zero-duration
interval. Leave unchecked for an occurrence with no end. Referenced ends cannot be removed.

(help-inspect-src-gui-widgets-temporal-range-widget-temporalrangewidget-setup-ui-self-range-button)=

**End date and duration** — Expand the Event's elapsed duration and end-date controls.
Date uncertainty remains a separate setting.

(help-inspect-src-gui-widgets-temporal-range-widget-temporalrangewidget-setup-ui-self-btn-lock-duration)=

**Duration** — Define the end by a fixed elapsed length from the start.

(help-inspect-src-gui-widgets-temporal-range-widget-temporalrangewidget-setup-ui-self-btn-lock-end)=

**End Date** — Give the end its own Manual date or Follow Event source. Changing
the start recalculates duration while preserving this end source.

(help-inspect-src-gui-widgets-temporal-range-widget-temporalrangewidget-setup-ui-self-enter-end-button)=

**Specify end date** — Switch to an independently authored end date instead of a
fixed duration.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-btn-new)=

**New...** — Open the creation menu to add an Event, Entity or map. Creating an entry is
separate from connecting it to another entry.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-new-menu)=

**New menu** — Open the New menu menu to choose a related operation. Opening the menu
does not apply any of its actions.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-action-create-event)=

**Create Event** — Create an Event at the viewed time. Naming, connections and map
placement remain separate choices.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-action-create-entity)=

**Create Entity** — Create an Entity with a chosen name and type, such as a character or
location.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-action-create-map)=

**Create Map** — Create and name a map from an image. Placing Event or Entity markers is
a separate action.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-btn-delete)=

**Delete** — Delete the selected entry from the world. This is different from clearing a
filter or hiding an item; review the confirmation and dependency warnings.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-show-context-menu-delete-action)=

**Delete selected entry** — Delete the selected world entry after confirmation.
Filtering or removing Longform membership instead retains the entry.

(help-inspect-src-gui-delegates-attribute-delegate-attributedelegate-createeditor-checkbox)=

**Boolean attribute** — Set this attribute to true or false. In historical editing,
saving corrects the displayed source; use the dated-change route to start a new state.

(help-inspect-src-gui-delegates-attribute-delegate-attributedelegate-createeditor-spinbox)=

**Numeric attribute** — Enter a numeric attribute value. In historical editing, saving
corrects the displayed source; it does not automatically create a new dated state.

(help-inspect-src-gui-widgets-authoring-context-widget-authoringcontextwidget-init-self-more-button)=

**Expand all / Collapse all** — Reveal every loaded World Context row, or return
each section to its first three rows. Counts refer to loaded entries. This does
not retrieve omitted facts, change the context mode or move the playhead.

(help-context-section-show-all)=

**Show all N / Show fewer** — Expand just this World Context section, or return
to its three-row preview. Timing and supporting Events remain beneath each fact.

(help-context-load-connections)=

**Load more connections / Retry connections** — Load another batch of saved
direct connections for the selected Entity, mode and date. Both directions and
custom names are included. Show all reveals loaded rows only; it does not fetch
another batch. The total stays unknown until checking finishes. Retry continues
a failed read; changed saved data restarts the browser. Loading does not edit
your description, move the playhead or add facts to AI Preview or Generate.

(help-inspect-src-gui-widgets-focus-writing-focuswritingcontroller-init-self-action)=

**Focus writing** — Enter or leave the focused writing presentation while retaining the
same live description, caret and scroll position.

(help-inspect-src-gui-widgets-focus-writing-focuswritingcontroller-make-surface-toolbar-button)=

**Writing toolbar** — Show or hide writing tools while staying in Focus writing.

(help-inspect-src-gui-widgets-focus-writing-focuswritingcontroller-make-surface-toc-button)=

**Writing contents** — Show or hide headings for navigating within the current
description.

(help-inspect-src-gui-widgets-focus-writing-focuswritingcontroller-make-surface-exit-button)=

**Exit focus** — Enter or leave the focused writing presentation while retaining the
same live description, caret and scroll position.

(help-inspect-src-gui-widgets-lore-duration-widget-loredurationwidget-create-spinbox-spin)=

**Duration component** — Set the indicated component of this elapsed duration. The
active calendar determines conversion to lore days.

(help-inspect-empty-eventlistwidget-init-74)=

**Create first Event** — Create an Event at the viewed time to begin building the
Timeline.

(help-inspect-empty-entityeditorwidget-build-editor-shell-165)=

**New Entity** — Create an Entity with a chosen name and type. Its connections are added
separately.

(help-inspect-empty-unifiedlistwidget-init-409)=

**Create Event** — Create an Event at the viewed time. Connections and map placement are
separate actions.

(help-inspect-empty-unifiedlistwidget-init-412)=

**Create Entity** — Create an Entity with a chosen name and type, such as a character,
location or faction.

(help-inspect-empty-eventeditorwidget-build-editor-shell-269)=

**New Event** — Create an Event at the viewed time, then edit its name, date and other
details.

(help-inspect-empty-entitylistwidget-init-80)=

**Create first Entity** — Create an Entity, such as a character, location or faction,
with a chosen name and type.

(help-inspect-view-src-gui-dialogs-context-tag-dialogs-contexttagreviewdialog-init-self-table)=

**Context-tag review** — Review suggested tag assignments, select proposals and choose
whether to accept or dismiss them.
