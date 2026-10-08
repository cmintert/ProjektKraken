"""Protect map working copies before replacing their authoring context."""

from collections.abc import Callable, Sequence
from typing import Any, Protocol

from PySide6.QtCore import QObject, SignalInstance


class MapEditOwner(Protocol):
    """Main-thread session boundary consumed by the transition guard."""

    transition_finished: SignalInstance

    def edit_status(self) -> dict[str, Any] | None:
        """Return an independent description of the active draft."""
        ...

    def apply_for_transition(self) -> None:
        """Submit the current draft through its command path."""
        ...

    def discard_for_transition(self) -> None:
        """Explicitly abandon the current draft."""
        ...


class MapEditTransitionCoordinator(QObject):
    """Resolve one draft and resume one approved action after acknowledgement."""

    def __init__(
        self,
        owners: Sequence[MapEditOwner],
        world_id: Callable[[], str],
        decide: Callable[[str, dict[str, Any]], str],
        feedback: Callable[[str], None],
        parent: QObject | None = None,
    ) -> None:
        """Compose the guard without a window or database dependency."""
        super().__init__(parent)
        self._owners = owners
        self._world_id = world_id
        self._decide = decide
        self._feedback = feedback
        self._continuation: Callable[[], None] | None = None
        self._waiting_session = ""
        self._waiting_command = ""
        self._waiting_world = ""
        self._deciding = False
        for owner in owners:
            owner.transition_finished.connect(self._on_finished)

    @property
    def is_waiting(self) -> bool:
        """Whether an approved action is waiting for persistence."""
        return self._continuation is not None

    def protects_object(self, object_id: str) -> bool:
        """Whether deleting a world entry would remove an active edit target."""
        return any(
            status is not None and status.get("object_id") == object_id
            for status in (owner.edit_status() for owner in self._owners)
        )

    def request_transition(self, reason: str, continuation: Callable[[], None]) -> None:
        """Prompt before meaningful loss; keep the first pending action."""
        if self.is_waiting or self._deciding:
            self._feedback("The map edit is still saving. Keep editing here for now.")
            return
        world = self._world_id()
        for owner in self._owners:
            status = owner.edit_status()
            if status is None:
                continue
            if status["pending"]:
                self._wait(owner, status, world, continuation)
                return
            if not status["dirty"] and not status["new"]:
                owner.discard_for_transition()
                continue
            self._deciding = True
            try:
                decision = self._decide(reason, status)
            finally:
                self._deciding = False
            current = owner.edit_status()
            if world != self._world_id() or current != status:
                self._feedback("The map edit changed. Please try the action again.")
                return
            if decision == "discard":
                owner.discard_for_transition()
            elif decision == "apply" and status["can_apply"]:
                self._wait(owner, status, world, continuation)
                owner.apply_for_transition()
                current = owner.edit_status()
                if self.is_waiting and current is not None:
                    self._waiting_command = str(current["command_id"] or "")
                    if not current["pending"]:
                        self._clear()
                return
            else:
                return
        if world == self._world_id():
            continuation()

    def _wait(
        self,
        owner: MapEditOwner,
        status: dict[str, Any],
        world: str,
        continuation: Callable[[], None],
    ) -> None:
        self._waiting_session = str(status["session_id"])
        self._waiting_command = str(status["command_id"] or "")
        self._waiting_world = world
        # Re-enter the guard after success: any additional owner must resolve too.
        self._continuation = lambda: self.request_transition(
            "continue the requested action", continuation
        )

    def _clear(self) -> None:
        self._continuation = None
        self._waiting_session = ""
        self._waiting_command = ""
        self._waiting_world = ""

    def _on_finished(self, result: dict[str, Any]) -> None:
        if not self.is_waiting or result["session_id"] != self._waiting_session:
            return
        if result["command_id"] != self._waiting_command:
            return
        continuation = self._continuation
        world_matches = self._waiting_world == self._world_id()
        self._clear()
        if result["success"] and world_matches and continuation is not None:
            continuation()
        elif not result["success"]:
            self._feedback("The map edit could not be applied. Your draft is retained.")
