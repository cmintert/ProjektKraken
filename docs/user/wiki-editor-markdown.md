# Wiki editor Markdown and links

(help-writing-edit)=

## Write in Rich or Markdown Source view

Event and Entity descriptions are stored as Markdown. Use **Rich view** for ordinary
prose and supported formatting, or **Markdown source** to edit the exact stored text.

1. Select an Event or Entity and place the caret in its description.
2. Use **Headings**, **Bold**, **Italic**, or the **Format** menu to format your writing.
3. Open **View → Markdown source** when you want to edit Markdown directly.
4. Choose **View → Rendered view** to return to Rich view when the content supports it.

Rich view supports paragraphs, headings from `#` through `###`, bold, italic and wiki
links. **Clear Formatting** removes heading, bold and italic formatting from the
selected text.

Descriptions containing tables, lists, code or other Markdown that Rich view cannot
safely preserve open in Source view. Those constructs remain editable and are saved
exactly; switching views does not convert them into supported Rich formatting.

**Example:** Write a character biography in Rich view. If you add a Markdown table of
titles and dates, continue editing it in Source view.

**Related:** {ref}`Wiki links <help-writing-links>` · {ref}`Focus writing
<help-writing-focus>` · {ref}`Add details <help-authoring-details>`

### Writing controls

The writing controls have three rows: **Edit / Insert / Format / View / Tools**,
compact formatting controls, and link/Focus writing actions. **Headings** offers
the existing heading styles. Bold, Italic and Clear Formatting have tooltips with
their existing shortcuts; full command names also appear in **Format**. The
previous **Body** command is named **Clear Formatting** to describe its existing
effect. It still clears heading/bold/italic formatting; no new Body operation was
added. **View** contains Markdown source/Rendered view and Table of contents;
**Tools** contains Spelling settings. Narrow rows use labeled **More actions**.

(help-writing-links)=

## Link to an entry without losing your writing

Wiki links connect words in a description to an Event or Entity. Use them to reference
people, places and events while keeping your prose readable.

1. Select words within one paragraph.
2. Choose **Link to entry…**.
3. Find the entry, select it and choose **Link**.

The selected words become the link’s label. With no selection, the entry’s name is
inserted at the caret. Cancelling preserves your text and selection; Undo reverses the
accepted link insertion.

Place the caret inside a link and choose **Peek link** to read its description without
leaving your writing. Choose **Open link** to visit its inspector. **Return to writing**
brings you back; navigation protects unfinished edits through **Save / Discard /
Cancel**.

You can also type `[[Name]]` before the entry exists. This preserves an unresolved
reference without requiring you to create anything.

A wiki link is a textual reference, not a specific relationship such as membership. If
**Auto-Create Relations from Wikilinks** is enabled, saving a resolved link also records
a `mentions` relation.

**Example:** Link “Ada’s coronation” to the coronation Event. Add a separate relation if
you also want to record Ada’s role in it.

**Related:** {ref}`Rich and Source writing <help-writing-edit>` · {ref}`Attributes,
relations and mentions <help-authoring-representations>` · {ref}`Create relations
<help-relations-create>`

### Navigation and exact source details

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
literal source. The **Rendered view** command in **View** switches back to Rich only after those constructs
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

(help-writing-spelling)=

## Configure spelling suggestions

Spelling settings choose the language and optional checking service used for
suggestions. Reviewing or ignoring a suggestion does not rewrite the description;
accepting a replacement edits the text. Provider credentials are settings, not world
content.

## Interface control reference

These explanations describe the software operation. Inspecting a control does not run it or read your entered values.

(help-inspect-src-gui-widgets-toc-widget-tocwidget-init-self-list-widget)=

**Description headings** — Choose a heading to navigate within the current description.

(help-inspect-src-gui-widgets-wiki-link-authoring-entrylinkpicker-init-self-search)=

**Find link target** — Search existing Events and Entities to insert a link into the
current writing.

(help-inspect-src-gui-widgets-wiki-link-authoring-entrylinkpicker-init-self-results)=

**Link targets** — Select an existing entry as the link target. Creating a link does not
assert an authored relation such as membership.

(help-inspect-src-gui-widgets-wiki-link-authoring-entrylinkpicker-init-self-link-button)=

**Link** — Insert a link to the selected existing entry, retaining selected prose as its
label. This does not create an authored relationship such as membership.

(help-inspect-src-gui-widgets-wiki-link-authoring-entrylinkpicker-init-cancel)=

**Cancel** — Cancel this Entry Link Picker operation without accepting its pending
changes. This is separate from applying or saving them.

(help-inspect-src-gui-widgets-wiki-peek-panel-wikipeekpanel-init-self-description)=

**Peek description** — Read the linked entry's description without leaving the current
writing. This preview is read-only.

(help-inspect-src-gui-widgets-wiki-peek-panel-wikipeekpanel-init-self-choices)=

**Ambiguous link targets** — Choose among entries that match this reference before
opening a target.

(help-inspect-src-gui-widgets-wiki-peek-panel-wikipeekpanel-init-self-open-button)=

**Open or edit link target** — Deliberately navigate to the linked entry's inspector.
Existing unfinished-writing safeguards still apply.

(help-inspect-src-gui-widgets-wiki-peek-panel-wikipeekpanel-init-self-create-entity-button)=

**Create Entity** — Create an Entity for this unresolved reference without leaving the
current writing. Creation is optional; open the new entry deliberately afterwards.

(help-inspect-src-gui-widgets-wiki-peek-panel-wikipeekpanel-init-self-create-event-button)=

**Create Event** — Create an Event for this unresolved reference without leaving the
current writing. This is separate from opening its inspector.

(help-inspect-src-gui-widgets-wiki-peek-panel-wikipeekpanel-init-self-close-button)=

**Close Peek** — Close the linked-entry preview and continue the current writing.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-setup-actions-self-action-bold)=

**Bold** — Apply or remove bold emphasis in the selected writing, or for text entered at
the caret.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-setup-actions-self-action-italic)=

**Italic** — Apply or remove italic emphasis in the selected writing, or for text
entered at the caret.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-setup-actions-self-action-h1)=

**H1** — Apply heading level 1 to the current writing paragraph. This changes
formatting, not the entry’s name.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-setup-actions-self-action-h2)=

**H2** — Apply heading level 2 to the current writing paragraph. This changes
formatting, not the entry’s name.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-setup-actions-self-action-h3)=

**H3** — Apply heading level 3 to the current writing paragraph. This changes
formatting, not the entry’s name.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-setup-actions-self-action-body)=

**Body** — Clear heading, bold and italic formatting from the selected writing. This
does not delete the selected words.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-contextmenuevent-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-contextmenuevent-ignore-action)=

**Ignore spelling suggestion** — Ignore this spelling finding without replacing the
authored words.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-add-link-menu-actions-action)=

**Link to entry…** — Choose an existing entry to link from the selected prose. With no
selection, its name is inserted at the caret; this does not assert membership or another
authored relationship.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-add-link-menu-actions-addaction)=

**Open link** — Navigate to the link target through the normal link workflow and its
unfinished-writing safeguards.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitexteditview-add-link-menu-actions-addaction-2)=

**Peek link (Alt+Click)** — Read the link target in the side pane without navigating
away from the current writing.

(help-inspect-src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-self-language-combo)=

**Spelling language** — Choose the language used by LanguageTool for spelling and
grammar checks.

(help-inspect-src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-self-username-edit)=

**LanguageTool username** — Enter the username for the configured LanguageTool account.
This is separate from the world author's name.

(help-inspect-src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-self-apikey-edit)=

**API Key:** — Enter the credentials required by the selected service. Help never reads
or displays the credential value. Saving settings is separate from making a request.

(help-inspect-src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-cancel-btn)=

**Cancel** — Cancel this SpellCheckSettings operation without accepting its pending
changes. This is separate from applying or saving them.

(help-inspect-src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-save-btn)=

**Save spelling settings** — Save the language and optional LanguageTool account
credentials.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitextedit-init-self-editor)=

**Description editor** — Edit the current description in Rich or Markdown Source mode.
Both presentations edit the same entry description.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitextedit-setup-link-controls-self-action-link-entry)=

**Link to entry…** — Choose an existing entry to link from the selected prose. With no
selection, its name is inserted at the caret; this does not assert membership or another
authored relationship.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitextedit-setup-link-controls-self-action-open-link)=

**Open link** — Navigate deliberately to the linked entry using the existing unfinished-
writing safeguards.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitextedit-setup-link-controls-self-action-peek-link)=

**Peek link** — Read the link target in the side pane without navigating away from the
current writing.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitextedit-setup-link-controls-self-action-return-writing)=

**Back to previous** — Return to the previous writing origin in the temporary link-
navigation trail. Draft safeguards still apply; discarded writing is not recovered.

(help-inspect-src-gui-widgets-wiki-text-edit-wikitextedit-setup-link-controls-self-return-button)=

**Back to writing** — Return to the previous writing origin in the temporary link-
navigation trail.

(help-inspect-src-gui-widgets-writing-toolbar-writingtoolbarpresentation-init-self-heading-button)=

**Heading style** — Choose body text or a heading level for the current paragraph.

(help-inspect-src-gui-widgets-writing-toolbar-writingtoolbarpresentation-view-actions-owner-action-toggle-mode)=

**Markdown source** — Toggle between Rendered HTML and Markdown Source.

(help-inspect-src-gui-widgets-writing-toolbar-writingtoolbarpresentation-view-actions-owner-action-toggle-toc)=

**Table of contents** — Show the headings available in the current description and
navigate within that writing.

(help-inspect-src-gui-widgets-writing-toolbar-writingtoolbarpresentation-view-actions-owner-action-spell-check)=

**Spelling settings** — Spell &amp; grammar check settings (LanguageTool).

(help-inspect-src-gui-widgets-writing-toolbar-writingtoolbarpresentation-build-menus-button)=

**Writing menu** — Open the indicated writing menu and inspect a specific item for its
effect.
