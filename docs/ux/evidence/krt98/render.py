"""Compare relation preparation with the original widgets, without opening a world.

Reuses the KRT-93 synthetic host, QSS, isolated settings and capture states.
PNG/geometry artifacts stay under ignored artifacts/krt98/{baseline,current}.
"""

import argparse
import subprocess
import sys
import types
from pathlib import Path


def main() -> None:
    """Load optional pre-extraction widgets and delegate the standard captures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref")
    options, remaining = parser.parse_known_args()
    if options.baseline_ref:
        # Load in dependency order so baseline authoring gets baseline captions.
        for name in ("connection_presentation", "relation_form", "relation_authoring"):
            module_name = f"src.gui.widgets.{name}"
            source = subprocess.check_output(
                [
                    "git",
                    "-c",
                    f"safe.directory={Path.cwd().as_posix()}",
                    "show",
                    f"{options.baseline_ref}:src/gui/widgets/{name}.py",
                ],
                text=True,
                encoding="utf-8",
            )
            module = types.ModuleType(module_name)
            sys.modules[module_name] = module
            exec(compile(source, f"baseline_{name}.py", "exec"), module.__dict__)
    from scripts.capture_connections_evidence import main as capture

    output = "artifacts/krt98/" + ("baseline" if options.baseline_ref else "current")
    sys.argv = [sys.argv[0], "--output", output, *remaining]
    capture()


if __name__ == "__main__":
    main()
