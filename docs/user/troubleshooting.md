# Troubleshooting

## The app does not start

Run `start-kraken.cmd` from a terminal. It performs an environment preflight
and reports missing requirements. Startup failures are written to
`logs/startup_error.log`; normal diagnostics are written to
`logs/kraken.log`.

## A saved layout prevents startup

Run:

```powershell
.\start-kraken.cmd --reset-settings
```

This clears saved interface preferences and the active-world selection. It does
not delete world folders.

## AI models are not listed

- Confirm LM Studio is running.
- Enter only the server address.
- Refresh models after loading or unloading a model in LM Studio.
- Generation and embedding may require different models.

## Raster editing has paused

Raster editing pauses when a save fails or the selected raster target becomes
stale. Read the visible error, reselect an existing Base or dated state, and
resume only after the underlying save problem is resolved.

## A dock seems to be missing

Check **View** and the tabs around the right and bottom dock areas. Use
**Layouts → Reset Layout** when necessary.

## Changes are not where expected

Confirm the active world in the title bar, the selected inspector item, the
active map, and the timeline playhead. Dated map content may change as the
playhead moves.

