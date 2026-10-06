# Events, Entities, and Relations

For the exact Markdown vocabulary, provisional links, and read-only Peek, see
[Wiki editor Markdown and links](wiki-editor-markdown.md).

## What this does

Events record what happens and when. Entities represent people, places,
factions, objects, and other things in the world. Relations connect any two
items with a named direction and optional details.

## Create an event or entity

1. Open the Explorer's **New** menu.
2. Select **Create Event** or **Create Entity**.
3. Select the new item in the Explorer.
4. Complete its inspector.

Event dates and durations use the active world calendar. Descriptions support
Markdown-style formatting and `[[Wiki Links]]`.

## Add details

Use the inspector to:

- edit the name, type, description, and custom attributes;
- add or remove tags;
- attach images and captions;
- review connected relations;
- use Fast Inject for structured text templates;
- request AI-assisted description work when a provider is configured.

Changes are saved after editing. Use **Edit → Undo** when you need to reverse a
supported content mutation.

## Attributes, relations, and mentions

These are different ways to express information about your world. Choose the
ones that suit your writing and modelling; they can coexist intentionally.

- **Attribute:** a named value on an entry, such as eye colour, population,
  allegiance, or an imported label. A value can contain another entry's name,
  but that name alone does not create a connection or a navigable link.
- **Relation:** an explicit connection between two entries. Its direction and
  kind express the connection you want to record. It can also carry notes,
  other details, and timing. The Graph uses relations to draw connections;
  which connections are visible depends on its filters and viewed time.
- **Mention in prose:** a reference within your writing. Ordinary text can
  mention a person or group without linking to its entry.
- **Linked mention:** a reference in prose that links to an entry. It lets you
  navigate to that entry. When **Auto-Create Relations from Wikilinks** is
  enabled, saving a resolved link also records a `mentions` relation. This
  records the reference; it does not assert membership, ownership, location,
  or another specific relationship.

### Examples

| What you want to express | What each representation gives you |
| --- | --- |
| Alice has grey eyes | An **Eye colour** attribute stores **Grey** as a value on Alice's entry. |
| Alice belongs to the Silver Guild | An **Affiliation** attribute can store the guild's name. A **Member of** relation explicitly connects Alice to the guild's entry. You may use either or both, depending on what you want to record. |
| Alice's biography discusses the Silver Guild | Plain prose records the discussion. A linked mention additionally lets you open the guild's entry; it does not by itself record membership. |
| Alice belonged to the guild during a particular period | A membership relation can carry start and end boundaries for connection views. A dated attribute can describe affiliation in Alice's historical record. These express different parts of the model and are edited separately. |
| A source lists Alice's affiliation as "Silver Guild" | An attribute can preserve that source's label even when the guild has no entry. An unresolved WikiLink can preserve a reference in prose while you write. |
| Alice joined the guild at a ceremony | An event can describe the joining, a relation can record membership, and prose can tell the story. You can combine them without one replacing the others. |

### Use several representations together

For a character's guild affiliation, you might store an affiliation attribute,
record a membership relation, and link to the guild in the biography. Each
serves its own purpose. Editing the affiliation value does not edit the
membership relation, and editing the relation does not rewrite the biography.

Kraken does not choose which account is true or keep independently authored
representations in sync. Differences may be deliberate, such as a quoted
claim alongside an uncertain relationship. When you intend them to describe
the same fact, review each representation when that fact changes.

For historical attribute editing, see
[View and correct an entity at another time](#view-and-correct-an-entity-at-another-time).
For relation timing, see
[Historical validity and uncertainty](#historical-validity-and-uncertainty).
For unresolved and stable links, see
[Wiki editor Markdown and links](wiki-editor-markdown.md).

## Set an event date or duration

The Event inspector starts with one clear date field. Type a date in the
world's calendar format and press **Enter** to apply it. If you change your
mind before applying the text, press **Escape** to restore the last accepted
date. You can also use the calendar button beside the field.

Choose **Date fields…** when you prefer separate year, month, and day
controls. Choose **Time…** to add a time of day.

For an event that lasts over time:

1. Check **Event has duration**, then open **End date / duration…**.
2. Choose whether changing the start should keep the **Duration** or the
   **End Date** fixed.
3. Enter a duration or an end date. If the start is only known to a year,
   **Specify an end date instead…** lets you enter a separately known end;
   the calculated midpoint end is not shown as an exact date.

Leave **Event has duration** unchecked for a single occurrence sometime within
a year. Unchecking it on an existing event clears its duration while keeping
the date's precision. On the Timeline, a hollow diamond marks a layout anchor
inside a dotted possible-date window; it does not assert the exact day. A
lasting event has a hatched possible extent; only a period when it is certainly
ongoing appears as a solid bar. Narrow windows use compact symbols when zoomed
out and regain their calendar width when zoomed in.

If a typed date is not recognized, it remains unchanged until you correct it,
choose a date from the calendar, or press **Escape**.

## View and correct an entity at another time

Move the Timeline playhead to see an entity as it appeared at that point in
your world's history. The Entity inspector shows the visible description and
attributes, along with a **Source** label and attribute tooltips that identify
where each value comes from.

You can correct the visible description or an existing attribute. The change
updates the source shown in the inspector, so a correction to a dated value
stays with that event while a baseline value remains part of the entity's
ordinary record.

When you add an attribute, choose whether it belongs to the **Entity baseline**
or begins **At this time**. For a dated change, choose an event at the viewed
time or create one. When removing a visible dated value, choose whether it
should be absent at this time or whether to remove the source override and
reveal the earlier value.

Use **Start a new description at this time** when a historical description
should begin with a new dated event rather than changing its current source.
Select **Return to Current Time** in the Timeline to move back to the world's
current story time.

## Focus on writing

When an Event or Entity is selected, choose **Focus writing** in the
description toolbar or press **F11**. The description moves into a centered
writing surface and the rest of the workspace dims.

Use **Formatting** or **Contents** in the focus surface when you need those
tools. To leave, select **Exit focus** in the focus surface, choose **Exit
focus** from the **View** menu, or press **F11** again. Your text, scroll
position, and normal inspector layout are restored.

## Create relations

Drag an event or entity onto another item to create a relation. Hold **Shift**
while dropping when you want to choose the relation type explicitly. You can
also edit relations from the selected item's inspector.

Relations are directional. Read the preview in the relation dialog to confirm
which item is the subject and which is the target.

## Historical validity and uncertainty

In a relation's **Temporal Settings**, choose a manual date, a named event,
**Date not known**, or **Unbounded** for its start and end. Unknown means the
boundary is unresolved; unbounded means that side has no limit. An end is
exclusive: the relation no longer holds at its end transition.

Bind an outgoing officeholder's end and a successor's start to the same event
when they share a handover. If the event is known only as `961`, both roles may
be possible during that year, but the shared transition establishes that they
do not overlap. Do not copy the event's displayed timeline coordinate into
two independent manual dates.

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
