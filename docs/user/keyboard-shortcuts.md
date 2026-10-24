(help-manual-shortcuts)=

# Keyboard Shortcuts

The current shortcuts are also available from
**Help → Keyboard Shortcuts…**.

Read the focus requirement with the action. For example, Ctrl+I creates an
Entity outside text editing, but applies Italic in a description. Ctrl+F
searches the focused text surface or Help rather than every open panel.

| Action | Shortcut |
| --- | --- |
| Help for current task | F1 |
| Explain the supported control under the pointer | Shift+F1 |
| Explain the focused control or highlighted menu action | Ctrl+Shift+F1 |
| Search the offline manual | Ctrl+F, while Help has focus |
| Return from Help to work | Escape, while Help has focus |
| Create event | Ctrl+E |
| Create entity, outside text editing | Ctrl+I |
| Create map | Ctrl+M |
| Undo | Ctrl+Z |
| Redo | Ctrl+Y or Ctrl+Shift+Z |
| Find in text | Ctrl+F |
| Next / previous control within the current panel | Tab / Shift+Tab |
| Next / previous visible panel region | F6 / Shift+F6 |
| Accept highlighted wiki-link suggestion | Enter |
| Open a wiki link | Ctrl+Click |
| Choose relation type while dropping | Shift+Drop |
| Bold | Ctrl+B |
| Italic, in description text | Ctrl+I |
| Heading 1, 2, or 3 | Ctrl+1, Ctrl+2, Ctrl+3 |
| Body text | Ctrl+0 |
| Focus writing / exit focus | F11 |
| Promote Longform item | Ctrl+[ |
| Demote Longform item | Ctrl+] |
| Cancel or deselect | Escape |
| Pan a map | Hold Space and drag |
| Delete selected trajectory point | Delete, while editing a trajectory |
| Apply trajectory changes | Enter, while editing a trajectory |
| Cancel trajectory changes | Escape, while editing a trajectory |

Some shortcuts apply only when the corresponding editor or map has keyboard
focus. **Escape** always cancels the most local active operation first. In the
trajectory editor it cancels an equalization preview, then an active date edit,
then the complete unsaved trajectory session. In Help, Escape hides search
before returning to work. During control inspection it dismisses inspection or
the explanation first, without canceling a map edit or leaving Focus writing.
**Help → Inspect control** provides the pointer route for supported fields,
buttons, menu actions and associated labels. Its targeting click explains the
operation without running it, including when the control is disabled.
Reordering and shifting are
controls within the active date edit and do not add separate shortcuts.

Tab dismisses wiki-link suggestions without accepting them. Use the writing
**Format → Indent / Outdent** and **Insert → Tab character** commands for deliberate
Source edits. See [panel keyboard navigation](workspace.md#move-between-panels-with-the-keyboard).
