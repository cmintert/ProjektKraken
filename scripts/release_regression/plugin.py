"""Opt-in child-process selection verification and durable pytest progress."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from scripts.release_regression.common import read


def event(kind: str, **values: Any) -> None:
    """Flush every record before Qt can abort the interpreter."""
    with Path(os.environ["PK_RELEASE_PROGRESS"]).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": kind, "time": time.time(), **values}) + "\n")
        stream.flush()


def pytest_collection_finish(session: pytest.Session) -> None:
    """Reject missing, added or reordered cases before test execution."""
    actual = [item.nodeid for item in session.items]
    event("collection", nodeids=actual)
    selection = os.environ.get("PK_RELEASE_SELECTION")
    # Diagnostic shared-process probes can record progress without certifying a
    # manifest. The release supervisor always supplies a frozen selection file.
    if selection and actual != read(Path(selection)):
        pytest.exit("Release module collection differs from frozen plan", returncode=4)


def pytest_deselected(items: list[pytest.Item]) -> None:
    """Selections must never silently narrow a release module."""
    pytest.exit(f"Unexpected release deselection: {len(items)}", returncode=4)


def pytest_runtest_logstart(nodeid: str, location: Any) -> None:
    """Persist the active test before setup."""
    event("start", nodeid=nodeid)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Any:
    """Identify setup hangs and aborts."""
    event("phase", nodeid=item.nodeid, phase="setup")
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Any:
    """Identify test-body hangs and aborts."""
    event("phase", nodeid=item.nodeid, phase="call")
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item: pytest.Item) -> Any:
    """Identify teardown hangs and aborts."""
    event("phase", nodeid=item.nodeid, phase="teardown")
    yield


def pytest_runtest_logreport(report: Any) -> None:
    """Retain phase failures, skip reasons and unexpected xfails."""
    event(
        "report",
        nodeid=report.nodeid,
        phase=report.when,
        outcome=report.outcome,
        reason=str(report.longrepr) if not report.passed else "",
        xfail=bool(getattr(report, "wasxfail", False)),
        seconds=report.duration,
    )


def pytest_runtest_logfinish(nodeid: str, location: Any) -> None:
    """Completion means teardown has finished, not merely a passing assertion."""
    event("finish", nodeid=nodeid)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Separate pytest completion from the parent-observed process exit."""
    event("session_finish", exitstatus=int(exitstatus))
