---
project: ProjektKraken
document: Main Project README
last_updated: 2026-10-23
---

# Projekt Kraken

**Plan events. Explore connections. See what changes over time.**

Projekt Kraken is a desktop application for organizing stories, histories, and
complex projects where time matters.

Whether you're planning a novel, writing a screenplay, documenting a roleplaying
campaign, building a fictional world, or researching historical events, Kraken
helps you keep track of what happens, when it happens, and how things connect.

[**Download Windows Beta**](https://github.com/cmintert/ProjektKraken/releases) ·
[**Getting Started**](docs/user/getting-started.md) ·
[**User Manual**](docs/user/index.md)

![Projekt Kraken workspace with timeline, map, and editing panels](<Screenshot 2026-10-20 094912.png>)

## What makes Kraken different?

### Time is part of your information

Events have dates, durations, and relationships. Dates can be precise,
approximate, or uncertain.

Move through the timeline to examine your project at different points in time.
Keep track of developments without treating every piece of information as
permanently true.

### People, places, and relationships change

A character changes allegiance. An organization gains influence. A city changes
hands.

Kraken lets you record these developments, connect them to events, and examine
the information relevant to a particular date.

Maps can also represent different geographical states across time.

### Chronology and narrative structure are separate

The order in which events happen isn't necessarily the order in which you tell
them.

Group events into parallel storylines or arcs using tags in the timeline.
Arrange written material in the [Longform editor](docs/user/longform.md) without
changing the underlying chronology.

Explore connections through the graph, or follow individual people, locations,
and events.

## What would you use it for?

| Use | Examples |
| --- | --- |
| **Novels & screenplays** | Character arcs, intersecting plots, flashbacks, continuity |
| **TTRPG campaigns** | Session history, factions, characters, evolving settings |
| **Worldbuilding** | Historical timelines, changing borders, cultures, relationships |
| **Historical research** | Chronologies, uncertain dates, source evidence, connected events |

These are different applications of the same idea: organizing information around
time and the connections between events.

Kraken doesn't write your story or simulate what happens next. You decide what
happens and why. The application helps you document, structure, and explore it.

## Try it yourself

The [Northwatch tutorial](docs/user/northwatch-tutorial.md) demonstrates a changing
setting: an army moves, borders shift, and leadership changes.

To create the sample world from a source checkout, follow the
[Northwatch setup guide](docs/ux/northwatch-demo.md#recreate-the-sample-for-maintainers).

## Download

**Projekt Kraken v0.20.1 Beta — Windows x64**

Download the [latest release](https://github.com/cmintert/ProjektKraken/releases),
extract the complete ZIP archive, and launch `ProjektKraken.exe`. Keep `_internal`
beside the executable.

No Python installation or cloud account is required. Your projects are stored
locally in portable world folders. [Optional AI features](docs/user/search-ai-and-analysis.md)
can be configured separately.

Kraken is under active development. Back up existing projects before upgrading.

[Installation instructions](docs/user/getting-started.md#install-and-launch) ·
[Release notes](docs/releases/0.20.1-beta1.md) ·
[Report an issue](https://github.com/cmintert/ProjektKraken/issues)

---

**Documentation:** [User Manual](docs/user/index.md) ·
[Contextual Help](docs/user/index.md#help-while-you-work) ·
[Developer Guide](docs/developer/index.md)

For source setup and contributions, see the
[development guide](docs/developer/development.md) and
[contributing guide](docs/developer/contributing.md).
Offline tools are documented in the [CLI reference](docs/reference/cli.md).

Open source · Python / PySide6 / SQLite · [GPLv3](LICENSE)
