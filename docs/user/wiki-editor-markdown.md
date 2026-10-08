# Wiki editor Markdown and links

Descriptions are stored as portable Markdown and `[[wiki links]]`. The editor
opens ordinary paragraphs, headings `#` through `###`, `**bold**`, `*italic*`,
and wiki links in Rich view. Single line breaks and blank lines are preserved.

Select words in an Event or Entity description and choose **Link to entry…**.
Search for an existing entry, select its row, then choose **Link**. Your selected
words remain the link's label. With no selection, the entry's name is inserted
at the caret. Duplicate names show the entry kind and an ID portion. Cancelling
keeps your text and selection; Undo reverses acceptance as one writing edit.
The action also appears in the writing context menu and stays available in
Focus writing. Narrow controls move secondary actions into **More actions**.

Place the caret inside a link to enable **Open link** or **Peek link**. Opening
an entry shows **Return to writing** in its inspector and writing controls.
Return restores your origin, selection, scroll, Rich/Source view and Focus
writing presentation. Both opening and returning protect unfinished edits with
**Save / Discard / Cancel**. Save waits for confirmation; Cancel keeps the draft;
Discard deliberately removes it. Return does not recover discarded writing.
Nested link visits return in order; choosing an unrelated entry ends this
temporary return trail. The trail is not retained between world sessions.

Selected text must fit within one paragraph and must not already contain links.
In Source, select words inside formatting rather than the Markdown marks.
Selections across unsupported source constructs are explained without changing
the text. Unsupported Markdown elsewhere in the description remains exact.
An entry rename keeps the link's identity and your authored label.

A WikiLink references an entry from prose; it does not assert membership or
another specific relationship. With **Auto-Create Relations from Wikilinks**
enabled, saving a resolved link also records a `mentions` relation. For the
distinction between values, explicit connections, and textual references, see
[Attributes, relations, and mentions](events-entities-relations.md#attributes-relations-and-mentions).

When a description contains a construct the Rich serializer cannot safely
round-trip, the editor opens **exact Markdown Source** instead. Lists,
blockquotes, tables, code spans and fences, standard Markdown links and images,
escapes, raw HTML, underscore emphasis, and deeper headings remain editable as
literal source. The HTML button switches back to Rich only after those constructs
are removed. Source text is saved and reopened exactly as entered. Rich view
does not claim to edit the larger Markdown vocabulary.

Type `[[Name]]` to keep an unresolved reference while writing. It saves without
requiring an object. Place the caret inside the link and choose **Open link**
or **Peek link** (use **More actions** when the writing controls are narrow).
**Ctrl+Click** also opens a missing target in the **Wiki Peek** pane;
**Alt+Click** peeks at it. A plain click places the caret without navigating.
Holding Alt over a wiki link shows an eye cursor for Peek; holding Ctrl shows
the hand cursor for Open. These cues work in Rich and Source views.
Choose **Create Entity** or **Create Event** in Wiki Peek to make the reference
an actual object. Creation is optional and undoable; it leaves the current
editor open. After creation, choose **Open / Edit** or follow the link again
to open the object deliberately. The link retains its
original spelling. A name link resolves once its name uniquely identifies an
object. Use completion to insert a stable `[[id:...|Name]]` link when identity
must survive renaming. Duplicate names appear as separate choices with object
kind and an ID prefix.

Use **Peek link**, **Alt+Click**, or **Peek link** in the context menu to read its
target in the side pane without changing the current selection. **Open / Edit**
deliberately navigates to that object and protects any unsaved draft. **Close
Peek** returns focus to the writing surface.

**Ctrl+Click** remains an accelerator for Open link. A plain name in prose is
not a link; linking it selects an existing entry and does not create a new
entry or an authored connection.

Peek currently shows a read-only text description. Rich media previews and
advanced Markdown editing are future product work; their source remains intact.
