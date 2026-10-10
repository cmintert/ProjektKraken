"""Serializable, content-free context for command operation diagnostics."""

from __future__ import annotations

import logging
import re
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from src.core.command import CommandResult

logger = logging.getLogger("src.operations")
SESSION_ID = str(uuid.uuid4())
_version = "unknown"
_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")


def configure(version: str) -> None:
    """Set build metadata once at launch, before operation events are emitted."""
    global _version
    _version = version


def safe_id(value: object) -> str:
    """Retain only bounded identifier syntax in ordinary diagnostics."""
    if isinstance(value, str) and _ID_PATTERN.fullmatch(value):
        if not value.lower().startswith(("sk-", "token-", "key-")):
            return value
    return ""


def new_trace(
    command: Any, action: str, world_id: str, epoch: int
) -> dict[str, str | int | float]:
    """Capture immutable request context without reading the worker database."""
    target_id = ""
    for field in ("entity_id", "event_id", "marker_id", "target_id", "map_id"):
        value = getattr(command, field, None)
        identifier = safe_id(value)
        if identifier:
            target_id = identifier
            break
    return {
        "operation_id": str(uuid.uuid4()),
        "command_id": safe_id(command.command_id),
        "command": command.__class__.__name__,
        "action": action,
        "world_id": safe_id(world_id),
        "target_id": target_id,
        "epoch": epoch,
        "requested_at": time.monotonic(),
    }


def from_request(request: object) -> dict[str, str | int | float] | None:
    """Read the optional serializable trace carried by a command request."""
    if not isinstance(request, dict):
        return None
    trace = request.get("trace")
    if not isinstance(trace, dict):
        return None
    if not all(
        isinstance(trace.get(key), str)
        for key in (
            "operation_id",
            "command_id",
            "command",
            "action",
            "world_id",
            "target_id",
        )
    ):
        return None
    if not isinstance(trace.get("epoch"), int) or not isinstance(
        trace.get("requested_at"), (int, float)
    ):
        return None
    return trace


def event(trace: dict[str, str | int | float], stage: str, **fields: object) -> None:
    """Record one bounded structured line containing IDs, never authored text."""
    base = (
        f"operation session={SESSION_ID} version={_version} "
        f"build={'packaged' if getattr(sys, 'frozen', False) else 'source'} "
        f"operation_id={trace['operation_id']} command_id={trace['command_id']} "
        f"command={trace['command']} action={trace['action']} "
        f"world_id={trace['world_id']} target_id={trace['target_id']} stage={stage}"
    )
    extra = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("%s%s", base, f" {extra}" if extra else "")


def finish(
    trace: dict[str, str | int | float] | None,
    result: CommandResult,
    *,
    outcome: str | None = None,
) -> CommandResult:
    """Attach trace to the result and record its terminal outcome."""
    if trace is not None:
        result.data.setdefault("command_id", str(trace["command_id"]))
        result.data["operation_trace"] = trace
        elapsed = max(
            0, round((time.monotonic() - float(trace["requested_at"])) * 1000)
        )
        event(
            trace,
            "terminal",
            outcome=outcome or ("succeeded" if result.success else "failed"),
            duration_ms=elapsed,
        )
    return result


def safe_stack(exc: BaseException) -> str:
    """Describe traceback locations without exception text or source lines."""
    frames = traceback.extract_tb(exc.__traceback__)[-12:]
    return " > ".join(
        f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" for frame in frames
    )
