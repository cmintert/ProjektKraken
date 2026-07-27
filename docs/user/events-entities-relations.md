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

