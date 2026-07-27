# Getting Started

## What this does

Each ProjektKraken world is a portable folder containing its lore database,
manifest, and assets. You can move or back up the whole folder without
separating its content.

## Install and launch

### Windows

1. Extract the application or open the source checkout.
2. Run `start-kraken.cmd`.
3. The launcher checks Python and required packages before opening the app.

For a source checkout on another platform, run `python -m src.app.main`.
ProjektKraken requires Python 3.13 or newer.

## Create or open a world

1. Open **File → Manage Databases…**.
2. Create a world or select an existing world folder.
3. Confirm the selection.
4. The active world name appears in the application title.

World folders are stored under `worlds/` in portable installations:

```text
worlds/
└── My World/
    ├── world.json
    ├── My World.kraken
    └── assets/
```

## First workflow

1. In the Explorer, open the **New** menu.
2. Create an event, entity, or map.
3. Select the new item to open its inspector.
4. Add a description, attributes, tags, images, or relations.
5. Open the Timeline, Map, Graph, or Longform dock when you need another view.

## Tips and gotchas

- Copy the entire world folder when transferring a world.
- Do not edit the `.kraken` file while the world is open.
- Use **File → Backup & Restore** before imports or large restructuring work.
- Use `start-kraken.cmd --reset-settings` when a damaged saved layout prevents
  the application from opening normally. This resets interface preferences,
  not the contents of your world.

