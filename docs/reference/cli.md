# Command-Line Interface

The unified entry point is:

```text
python -m src.cli.cli --help
```

Available modules include:

- `event`
- `entity`
- `relation`
- `map`
- `attachment`
- `calendar`
- `timeline`
- `wiki`
- `index`
- `longform`
- `obsidian`
- `backup`
- `graph`
- `info`

Example:

```text
python -m src.cli.cli event list --database "worlds/My World/My World.kraken"
python -m src.cli.cli entity create --database "world.kraken" --name "Mara" --type character
python -m src.cli.cli graph export --database "world.kraken" --out-file "graph.json"
```

Individual modules can also be run directly, for example
`python -m src.cli.event --help`.

The CLI is intended for automation and direct world maintenance. It does not
provide feature parity with every interactive map, raster, AI, or analysis
workflow.

