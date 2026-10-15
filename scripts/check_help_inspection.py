"""Check explicit inspection coverage and reviewed behavior fingerprints."""

from __future__ import annotations

import sys
from pathlib import Path

from src.core.help_inspection_inventory import check_inventory


def main() -> int:
    """Fail with actionable review diagnostics without changing source or records."""
    errors = check_inventory(Path(__file__).resolve().parents[1])
    if errors:
        sys.stderr.write("\n".join(errors) + "\n")
    else:
        sys.stdout.write(
            "Inspection declarations, excerpts and source reviews agree.\n"
        )
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
