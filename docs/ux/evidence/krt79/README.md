# KRT-79 writing-tool disclosure evidence

The Summary… and Draft with AI… actions use the shared quiet control role
(`StyleHelper.get_action_role_style("quiet", ...)`). A right arrow identifies a
closed panel; a down arrow and the theme's checked surface identify an open one.
The arrow uses `supporting_text` when closed and `action_quiet_checked_text` when
open. No object-identity color is used for either writing action. This follows
authoring contracts 6, 7 and 8 without changing the interaction contract.

The buttons remain separate toggles. Space and click open or close the respective
panel without generating, saving, moving the description caret, or removing an
unfinished Summary or AI prompt. Their accessible names retain the full action
labels; their descriptions now begin with “Collapsed” or “Expanded” and continue
with the tool's purpose. Checkable state and tooltip remain available. This is
programmatic accessibility evidence, not a screen-reader session.

## Rendered states

The [capture manifest](captures.json) records the pre-change commit, source hashes,
environment, layout measurements and hashes for the eight retained PNGs. The
isolated capture script used synthetic Entity/Event data, never a personal world or
database. Reproduce with:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.venv\Scripts\python.exe -m scripts.capture_inspector_evidence --output tmp/krt79-review --widths 360 871 --states support summary ai_draft writing_panels
```

| State | Dark | Light |
| --- | --- | --- |
| Entity, 360 px, closed | [Closed](entity-dark_mode-360-support.png) | [Closed](entity-light_mode-360-support.png) |
| Entity, 360 px, open | [Both open, focus](entity-dark_mode-360-writing_panels.png) | [Summary open](entity-light_mode-360-summary.png) |
| Event, 360 px, AI open | [AI open](event-dark_mode-360-ai_draft.png) | [AI open](event-light_mode-360-ai_draft.png) |
| Event, 871 px, both open | [Both open, focus](event-dark_mode-871-writing_panels.png) | [Both open, focus](event-light_mode-871-writing_panels.png) |

The retained 360 px captures report zero horizontal scroll. Existing tests cover
independent simultaneous panels, in-progress Summary/AI input, description
selection and caret, undo, split/return, and narrow reflow. KRT-79 tests add
keyboard state, accessible descriptions and theme token checks for normal,
hover, focus, checked and disabled control states. The shared quiet role owns
those states; the arrow does not replace hover, focus or disabled styling.

Offscreen renders show layout and color in the sampled states. On 2026-10-10,
the user confirmed **human approval of KRT-79** after the implementation commit
`c13a8232`. This is a reported human review pass, separate from the automated
checks. No review recording, route-coaching details, measured native dimensions,
or actual screen-reader output were supplied; the captures and accessibility
checks above retain their own narrower claims. KRT-45's matched KA-01–20
comparison is separate and remains pending.
