---
project: ProjektKraken
document: Large-World Performance Measurement
last_updated: 2026-09-15
---

# Large-World Performance Measurement

The performance suite is an opt-in diagnostic tool. It generates disposable data,
automates measured application interactions, and writes reports. It does not modify
source code, select optimizations, update baselines, or open a real world in Kraken.

## Run it

From the repository root on Windows:

```powershell
.venv\Scripts\python.exe -m src.performance.runner --quick --target source
```

Run the complete profile matrix:

```powershell
.venv\Scripts\python.exe -m src.performance.runner --full --target source
```

Measure an existing packaged build separately:

```powershell
.venv\Scripts\python.exe -m src.performance.runner --quick --target packaged
```

The default packaged location is `dist/ProjektKraken/ProjektKraken.exe`. Use
`--packaged-executable PATH` for another build. Add `--visible` to display the
automated window, `--keep-fixture` to retain generated data, or
`--compare tmp/performance/<run>/metrics.json` to compare without changing that
report.

Quick mode uses the 10,000-event / 25,000-entity standard profile. Full mode also
tests dense dates, relation-heavy data, large content, and temporal-map data. Full
runs take substantially longer.

## Outputs and isolation

Every run writes only to `tmp/performance/<run-id>/` and labels its outputs
**MEASUREMENT ONLY**:

- `summary.md`: readable timing and comparison summary.
- `metrics.json`: normalized metrics and raw samples.
- `run-manifest.json`: environment, fixture provenance, status, and integrity proof.
- Per-profile probe, stdout, stderr, settings, logs, and optional retained fixture.

The runner redirects QSettings, application logs, and the fallback worlds directory
into the run folder. Generated databases are deleted unless `--keep-fixture` is
given. Before and after the run, it hashes Git-tracked files and databases under the
repository's real `worlds/` directory. Any difference makes the run fail.

Use `Ctrl+C` to stop a run. Completed profiles and partial failure information remain
available in the run directory. No report is promoted to a baseline automatically.

