# ProjektKraken CLI

The maintained command reference is [docs/reference/cli.md](../../docs/reference/cli.md).

Run the CLI from a source checkout with Python 3.13 or newer and the project
dependencies installed. The unified entry point is `python -m src.cli.cli`;
individual `python -m src.cli.<module>` invocations remain supported.
Close the desktop application before writing to a world database.

For example, with an existing world folder:

```text
python -m src.cli.cli entity list --database "worlds/My World/My World.kraken" --json
python -m src.cli.entity create --database "worlds/My World/My World.kraken" --name Mara --type character --json
```

The source CLI uses Qt dependencies. It is not shipped as a separate Windows
executable and does not cover every desktop feature.
