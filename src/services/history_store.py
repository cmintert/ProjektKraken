"""Ordered, fail-closed persistent undo/redo state; no Qt or command imports."""

import json
import sqlite3
from typing import Any

from src.services.migrations.schema import HISTORY_COMMAND_ID_EXPRESSION

HISTORY_KEY = "command_history_stacks_v2"
STACK_LIMIT = 100
HISTORY_VERSION = 2


def empty_manifest() -> dict[str, Any]:
    """Return a new restart boundary without sharing mutable stack lists."""
    return {"version": 2, "undo": [], "redo": []}


class HistoryStore:
    """Operate inside a caller-owned transaction; the manifest is authoritative."""

    def __init__(self, connection: sqlite3.Connection, world_id: str) -> None:
        """Bind only the owning worker's SQLite connection and world identity."""
        self.connection = connection
        self.world_id = world_id
        self.key = f"{HISTORY_KEY}:{world_id}"

    def read(self) -> dict[str, Any]:
        """Reject malformed metadata rather than skipping unreachable commands."""
        row = self.connection.execute(
            "SELECT value FROM system_meta WHERE key=?", (self.key,)
        ).fetchone()
        if row is None:
            if self.connection.execute(
                "SELECT 1 FROM command_history WHERE world_id=? LIMIT 1",
                (self.world_id,),
            ).fetchone():
                raise ValueError("Persistent history manifest is missing")
            return empty_manifest()
        state = json.loads(row[0])
        if not isinstance(state, dict) or state.get("version") != HISTORY_VERSION:
            raise ValueError("Unsupported persistent history manifest")
        ids: list[str] = []
        for name in ("undo", "redo"):
            stack = state.get(name)
            if not isinstance(stack, list) or len(stack) > STACK_LIMIT:
                raise ValueError("Invalid persistent history stack")
            if any(not isinstance(k, str) or not k for k in stack):
                raise ValueError("Invalid persistent command identity")
            ids.extend(stack)
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate persistent command identity")
        return state

    def write(self, state: dict[str, Any]) -> None:
        """Persist stack order atomically with its command rows."""
        self.connection.execute(
            "INSERT INTO system_meta(key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (self.key, json.dumps(state)),
        )

    def rows(self) -> dict[str, sqlite3.Row]:
        """Index active rows, ignoring archived rows outside the manifest."""
        state = self.read()
        needed = set(state["undo"] + state["redo"])
        if not needed:
            return {}
        result = {}
        placeholders = ",".join("?" for _ in needed)
        for row in self.connection.execute(
            f"SELECT * FROM command_history WHERE world_id=? "
            f"AND {HISTORY_COMMAND_ID_EXPRESSION} IN ({placeholders})",
            (self.world_id, *sorted(needed)),
        ):
            try:
                payload = json.loads(row["command_data"])
                identity = payload.get("_command_base", {}).get("command_id")
            except (ValueError, AttributeError):
                continue
            if not isinstance(identity, str):
                continue
            if identity in needed:
                if identity in result:
                    raise ValueError("Duplicate active history record")
                result[identity] = row
        if needed != result.keys():
            raise ValueError("Persistent history references missing command records")
        return result

    def append(self, identity: str) -> None:
        """Start a new branch and retain the newest bounded undo suffix."""
        state = self.read()
        if identity in state["undo"] + state["redo"]:
            raise ValueError("Command is already in persistent history")
        state["undo"] = (state["undo"] + [identity])[-STACK_LIMIT:]
        state["redo"] = []
        self.write(state)

    def move(self, identity: str, executed: bool, payload: str | None = None) -> None:
        """Move only the current stack top; persist fresh command state too."""
        state = self.read()
        source, target = ("redo", "undo") if executed else ("undo", "redo")
        if state[source][-1:] != [identity]:
            raise ValueError("Persistent history action is out of order")
        row = self.rows()[identity]
        self.connection.execute(
            "UPDATE command_history SET is_executed=?, command_data=? WHERE id=?",
            (int(executed), payload or row["command_data"], row["id"]),
        )
        state[source].pop()
        state[target].append(identity)
        self.write(state)

    def boundary(self) -> None:
        """Prevent restart traversal across an unrestorable session-only action."""
        self.write(empty_manifest())

    def retire_sessions(self, kept: list[str]) -> None:
        """Retain only contiguous reachable stack suffixes after session pruning."""
        state = self.read()
        rows = self.rows()
        for name in ("undo", "redo"):
            removed = [
                i
                for i, key in enumerate(state[name])
                if rows[key]["session_id"] not in kept
            ]
            if removed:
                state[name] = state[name][max(removed) + 1 :]
        self.write(state)
