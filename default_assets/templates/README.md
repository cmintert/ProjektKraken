# Task Prompt Templates

ProjektKraken separates the world persona from reusable authoring tasks. Bundled
tasks are read-only application assets; custom tasks are stored in the active
world's portable AI preferences.

## Bundled task format

Bundled files live in `task_prompts/` and use a metadata header followed by the
task text:

```text
---
version: 1.0
template_id: revise_clarity_flow
name: Revise — Clarity and Flow
description: Improve an existing description without changing its facts
intent: update
---

Return the complete revised description of {name} ...
```

Required metadata fields are `version`, `template_id`, `name`, and `intent`.
Supported intents are `create`, `update`, and `general`.

Task text may use only these variables:

- `{name}`
- `{type}`
- `{description}`
- `{lore_date}`

RAG and spatial context are injected as separate data blocks and are not template
variables. The configured Persona remains the system prompt and is never replaced
by a task.

## Ownership and editing

- Bundled tasks are loaded from `task_prompts/`, are read-only, and can be
  duplicated into the active world.
- World tasks use UUID identifiers, update in place, and travel with the world
  database.
- `system_prompts/` contains the retired v1 library solely for non-destructive
  legacy migration. Unknown legacy families are copied into each world when its AI
  preferences are upgraded; the source files are not deleted.

Use **Tools → AI Settings → Task Templates** to create, edit, duplicate, or delete
world tasks. In an entity or event editor, choose a task and select **Use Template**
to copy it into the editable draft.
