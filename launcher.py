"""ProjektKraken source and PyInstaller launcher."""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.app.startup_check import (  # noqa: E402
    check_environment,
    format_environment_error,
    report_startup_failure,
    report_unhandled_startup_exception,
)
from src.core.runtime_diagnostics import (  # noqa: E402
    install_runtime_diagnostics,
    record_startup_exception,
    shutdown_runtime_diagnostics,
)


def run() -> int:
    """Validate the source environment and start the application."""
    if not getattr(sys, "frozen", False):
        check = check_environment()
        if not check.ok:
            report_startup_failure(format_environment_error(check))
            return 1

        if "--check" in sys.argv:
            print(f"Environment OK: Python {sys.version.split()[0]}")
            return 0

    install_runtime_diagnostics()
    try:
        from src.app.entry import main

        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    except BaseException as exc:
        record_startup_exception(exc)
        try:
            report_unhandled_startup_exception(exc)
        except Exception:
            pass
        return 1
    finally:
        shutdown_runtime_diagnostics()
    return 0


if __name__ == "__main__":
    sys.exit(run())
