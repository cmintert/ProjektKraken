"""Manual entry point for the large-world measurement suite."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.performance.runner import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
