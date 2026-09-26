# Wiki editor Markdown and links

Descriptions are stored as portable Markdown and `[[wiki links]]`. The editor
opens ordinary paragraphs, headings `#` through `###`, `**bold**`, `*italic*`,
and wiki links in Rich view. Single line breaks and blank lines are preserved.

When a description contains a construct the Rich serializer cannot safely
round-trip, the editor opens **exact Markdown Source** instead. Lists,
blockquotes, tables, code spans and fences, standard Markdown links and images,
escapes, raw HTML, underscore emphasis, and deeper headings remain editable as
literal source. The HTML button switches back to Rich only after those constructs
are removed. Source text is saved and reopened exactly as entered. Rich view
does not claim to edit the larger Markdown vocabulary.

Type `[[Name]]` to keep an unresolved reference while writing. It saves without
requiring an object. Click an unresolved link to see its provisional state in
the **Wiki Peek** pane; creating an Entity or Event there is optional and
undoable. Creation leaves the current editor open and retains the link's
original spelling. A name link resolves once its name uniquely identifies an
object. Use completion to insert a stable `[[id:...|Name]]` link when identity
must survive renaming. Duplicate names appear as separate choices with object
kind and an ID prefix.

Use **Alt+Click** on a link, or **Peek link** in its context menu, to read its
target in the side pane without changing the current selection. **Open / Edit**
deliberately navigates to that object and protects any unsaved draft. **Close
Peek** returns focus to the writing surface.

Peek currently shows a read-only text description. Rich media previews and
advanced Markdown editing are future product work; their source remains intact.
