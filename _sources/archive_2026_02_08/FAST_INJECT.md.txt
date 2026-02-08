# Fast Inject Service

The Fast Inject service provides a powerful templating system for quickly generating and injecting entities, events, and complex data structures into the ProjektKraken world.

## Overview

Fast Inject allows you to define templates in JSON format (`.fastinject`) that can be resolved through a dynamic UI and applied to your project. It supports variables, choices, and complex nested data structures.

## Template Structure

Templates are defined using the `FastInjectTemplate` dataclass.

### Attributes
Attributes can be simple values or complex nested structures (dictionaries and lists).
- **Simple**: `"Age": 12`
- **Nested Dict**: `"Details": {"HP": 100, "MP": 50}`
- **Nested List**: `"Inventory": ["Sword", "Shield"]`

### Variables
Templates support dynamic resolution through variables:
- **Open Variable**: `{{VAR_NAME}}` (Prompt for input)
- **Choice Variable**: `{{VAR:Option1|Option2|Option3}}` (Renders as a dropdown)

Variables can be embedded within strings:
`To {{GoalVerb:find|destroy|protect}} the {{GoalObject}}.`

## FastInjectDialog (UI)

The UI provides a unified editor with two tabs:

### 1. Configure Tab
- **Flattened View**: Complex structures are flattened into individual rows for easy editing (e.g., `Details.HP`, `Inventory[0]`).
- **Smart Widgets**: 
  - Pure variables with choices → **Dropdowns**
  - Pure variables without choices → **Text Inputs**
  - Mixed content → **Live Result Preview** with sub-controls for each variable.
- **Selection**: Use checkboxes at the end of each row to include/exclude specific attributes.

### 2. Edit Source Tab
- Direct access to the raw JSON of the template.
- Supports saving manual changes directly to the template file on disk.

## Resolution Logic

When applying a template:
1. **Flattening**: The template is decomposed into simple scalar rows for the UI.
2. **Editing**: User interacts with dropdowns and text fields.
3. **Reconstruction**: The service rebuilds the original nested dictionary/list structure from the flattened keys.
4. **Type Restoration**: Integer values are automatically restored from strings.
5. **Application**: The resolved template is applied to the target entity or project.

## File Support
Templates are typically saved with the `.fastinject` extension and can be imported/exported through the UI.
