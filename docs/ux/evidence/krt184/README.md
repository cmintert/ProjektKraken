# Scoped Authoring and direct graph creation verification

Scoped Authoring adds a world-specific scope and a keyboard and canvas route
for creating relationships. This record covers the implementation working
copy on 23 November 2026.
[KRT-184](https://linear.app/projektkraken/issue/KRT-184/implement-scoped-authoring-and-direct-relations-graph-creation)

## Authoring and presentation

- Contracts 2, 4, 5, 6, 7, 8, 9, and 11 apply. **Authoring Scope** is reachable
  from the status bar and View menu. **Connect…** opens the canvas handle's
  draft from the keyboard. The focused control owns Enter. Scope changes
  cancel unfinished graph drafts while submitted operations retain their
  originating world.
- The graph handle uses the shared mode and focus colors. Dialog actions use
  the shared action roles. Status copy identifies saved, rejected, filtered,
  and outside-scope outcomes. The two touched graph presentation paths moved
  from hardcoded fallback colors to theme roles, allowing six legacy visual
  exceptions to be removed.
- A Windows Qt probe at 380 logical pixels exercised dark and light themes,
  visible focus, the disabled creation action, and Enter ownership in the
  type field and on the confirmation button.

## Verification

- The automated Windows Qt journey started in a disposable empty world. It
  exercised Follow Scope creation tags, choosing both endpoints from the
  keyboard, creating an Event with its relationship, seeing saved feedback,
  retaining the playhead across a scope change, and undoing and redoing the
  Event. An outside-scope endpoint stayed hidden until a separate membership
  edit, which was then undone. Both probes used the real worker and persistent
  command history.
- An isolated WebEngine regression exercises bridge payloads with synthetic
  pointer events. It checks graph positions after creation, filtering and
  restoration. Transaction tests inject failures in reciprocal insertion,
  history recording, and undo. Separate tests exercise Search ranking,
  Timeline reveal, command recovery, and obsolete graph replies.

## Documentation and acceptance

- The workspace and graph guides describe task routes for authors who already
  know Entities and Events. Timeline and graph control excerpts describe
  the new actions and their effects. Existing Help topics and anchors remain
  available.
- Offline Help generation resolved all ten new contextual excerpts. The
  repository-wide inspection check identified two stale Database Manager
  source reviews that also appear on the starting revision.
- Independent reader review, live Help acceptance, and the human authoring
  benchmark are pending.
