"""Command compensation follows the outer command/history transaction."""

import hashlib
import json
import logging
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class _Scope:
    database: object
    restore_retry_state: bool = False
    committed: list[Callable[[], None]] = field(default_factory=list)
    rolled_back: list[Callable[[], None]] = field(default_factory=list)
    files: dict[Path, Path | None] = field(default_factory=dict)
    expected_files: dict[Path, str | None] = field(default_factory=dict)
    backup: Path | None = None
    retain_backup: bool = False


_scope: ContextVar[_Scope | None] = ContextVar("command_transaction", default=None)


@contextmanager
def command_transaction(
    database: Any, *, restore_retry_state: bool = False
) -> Iterator[None]:
    """Share a transaction and defer compensation until its actual outcome."""
    active = _scope.get()
    if active is not None and active.database is database:
        yield
        return
    current = _Scope(database, restore_retry_state=restore_retry_state)
    token = _scope.set(current)
    try:
        with database.transaction():
            yield
    except Exception:
        _rollback(current)
        raise
    else:
        _notify(current.committed)
    finally:
        _scope.reset(token)
        if current.backup is not None and not current.retain_backup:
            try:
                shutil.rmtree(current.backup)
            except OSError:
                logger.warning("Temporary command files retained at %s", current.backup)


def preserve_files(*paths: Path) -> None:
    """Journal touched assets only; callers must validate their managed paths first."""
    active = _scope.get()
    if active is None:
        return
    for supplied in paths:
        path = supplied.resolve()
        if path in active.files:
            continue
        if not path.exists():
            active.files[path] = None
            active.expected_files[path] = None
            continue
        if active.backup is None:
            active.backup = Path(tempfile.mkdtemp(prefix="kraken-command-"))
        target = active.backup / str(len(active.files))
        shutil.copy2(path, target)
        active.files[path] = target
        active.expected_files[path] = _file_digest(target)


def _file_digest(path: Path) -> str | None:
    if not path.exists():
        return None
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def record_file_changes(*paths: Path) -> None:
    """Record managed writes so rollback can distinguish independent replacements."""
    active = _scope.get()
    if active is None:
        return
    for supplied in paths:
        path = supplied.resolve()
        if path in active.files:
            active.expected_files[path] = _file_digest(path)


def _rollback(active: _Scope) -> None:
    hook_error = None
    try:
        _notify(reversed(active.rolled_back), strict=True)
    except Exception as exc:
        hook_error = exc
    try:
        _restore_files(active)
    except Exception as exc:
        _retain_recovery(active)
        if hook_error is not None:
            raise hook_error from exc
        raise
    if hook_error is not None:
        _retain_recovery(active)
        raise hook_error


def _restore_files(active: _Scope) -> None:
    try:
        conflicts = _file_conflicts(active)
        for path, backup in reversed(active.files.items()):
            if path in conflicts:
                continue
            if backup is None:
                if (
                    not conflicts
                ):  # Retain command artifacts when another path conflicts.
                    path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, path)
    except OSError as exc:
        _retain_recovery(active)
        raise RuntimeError(
            f"Asset rollback failed; recovery files retained at {active.backup}"
        ) from exc
    if conflicts:
        _retain_recovery(active)
        raise FileExistsError(
            "Independent files prevent rollback: " + ", ".join(map(str, conflicts))
        )


def _file_conflicts(active: _Scope) -> set[Path]:
    conflicts = set()
    for path, backup in active.files.items():
        actual = _file_digest(path)
        original = _file_digest(backup) if backup is not None else None
        if actual not in (original, active.expected_files[path]):
            conflicts.add(path)
    return conflicts


def capture_command_state(command: Any) -> dict[str, Any]:
    """Preserve retry state, retaining opaque third-party values by reference."""
    active = _scope.get()
    if active is None or not active.restore_retry_state:
        return {"_is_executed": command._is_executed}
    state = {}
    for key, value in command.__dict__.items():
        try:
            state[key] = deepcopy(value)
        except TypeError:
            state[key] = value
    return state


def _retain_recovery(active: _Scope) -> None:
    active.retain_backup = True
    if active.backup is not None:
        manifest = {
            str(path): str(backup) if backup else None
            for path, backup in active.files.items()
        }
        (active.backup / "recovery.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        logger.error("Command asset recovery retained at %s", active.backup)


def _notify(callbacks: Any, *, strict: bool = False) -> None:
    errors = []
    for callback in callbacks:
        try:
            callback()
        except Exception as exc:
            logger.exception("Command transaction compensation failed")
            errors.append(exc)
    if strict and errors:
        raise errors[0]


def after_command(
    committed: Callable[[], None], rolled_back: Callable[[], None]
) -> None:
    """Register hooks inside a command transaction, including nested commands."""
    active = _scope.get()
    if active is None:
        raise RuntimeError("Command outcome hooks require an active transaction")
    active.committed.append(committed)
    active.rolled_back.append(rolled_back)
