# Events, Entities, and Relations

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

## Set an event date or duration

The Event inspector starts with one clear date field. Type a date in the
world's calendar format and press **Enter** to apply it. If you change your
mind before applying the text, press **Escape** to restore the last accepted
date. You can also use the calendar button beside the field.

Choose **Date fields…** when you prefer separate year, month, and day
controls. Choose **Time…** to add a time of day.

For an event that lasts over time:

1. Choose **End date / duration…**.
2. Choose whether changing the start should keep the **Duration** or the
   **End Date** fixed.
3. Enter a duration or an end date. The summary shows the resulting span.

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
