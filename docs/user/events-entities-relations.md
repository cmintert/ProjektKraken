# Events, Entities, and Relations

For the exact Markdown vocabulary, provisional links, and read-only Peek, see
[Wiki editor Markdown and links](wiki-editor-markdown.md).

## What this does

Events record what happens and when. Entities represent people, places,
factions, objects, and other things in the world. Relations connect any two
items with a named direction and optional details.

(help-authoring-create)=

## Create an event or entity

An **Event** records something that happens, such as a coronation or battle. An
**Entity** represents something in your world, such as a person, place or faction.

1. Open the Explorer’s **New** menu.
2. Choose **Create Event** or **Create Entity**.
3. Enter a name. For an Entity, also choose its type.
4. Select the new item in the Explorer to add descriptions, attributes and other details.

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

An event’s date records when it happens. Its duration records how long it lasts. An
uncertain date does not, by itself, mean the event has a duration.

1. Select the Event and enter its date using the world’s calendar.
2. Press **Enter**, or leave the date field, to validate the input.
3. Use **Date details & uncertainty…** for separate year, month and day controls.
4. If the event lasts over time, enable **Event has duration** and open **End date / duration…**.

Choose **Duration** to preserve the elapsed length when changing the start. Choose **End
Date** to preserve the end and recalculate the duration. For a year-only start with a
separately known end, use **Specify an end date instead…**.

Validation accepts the date locally; it does not confirm a save. Check the separate save
status, or use **Save Changes**. Invalid or unfinished date input is not saved. Press
**Escape** in an unaccepted date field to restore its last accepted value.

**Example:** A coronation known only to have occurred in 962 needs a year-only date, not
a year-long duration. A siege lasting thirty days needs a duration as well as a start
date.

**Related:** {ref}`Date precision <help-date-precision>` · {ref}`Date evidence
<help-date-evidence>` · {ref}`Chronology <help-event-chronology>` · {ref}`Timeline
viewing <help-timeline-viewing>`

(help-control-event-timing)=

> Duration records how long an event lasts, independently of how precisely its start is known. Enable Event has duration to enter a duration or a separately known end date. Keep Duration preserves the elapsed length when you change the start; Keep End Date preserves the end and changes the elapsed length. A year-only occurrence does not need a duration merely because its exact day is unknown. Removing a duration retains the start's date precision. Validate the date locally, then check the separate save status before treating an edit as saved.

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
2. Choose **Connected to…**, then choose an existing target.
3. Review the connection and select **Connect** to save, or **Cancel** to discard.
4. Select a saved relation and choose **Refine relation…** to adjust its meaning and details.

You can also drop an existing Event or Entity onto the labeled connection target. In
this workflow, the **dropped entry is the source** and the **inspected entry is the
target**. Review that direction before connecting. Dropping elsewhere in the inspector
does not create a relation.

For advanced options and custom relation types, use **More actions → Add detailed
relation…** or **Full relation editor…**.

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
