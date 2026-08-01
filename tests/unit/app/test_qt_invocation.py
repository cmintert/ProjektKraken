"""Tests for typed Qt invocation helpers."""

import pytest
from PySide6.QtCore import Q_ARG, QObject, Slot

from src.app.qt_invocation import invoke_queued


class _Receiver(QObject):
    """Record values delivered through a queued Qt slot."""

    def __init__(self) -> None:
        super().__init__()
        self.values: list[str] = []

    @Slot(str)
    def receive(self, value: str) -> None:
        """Record a delivered value."""
        self.values.append(value)


@pytest.mark.real_qt_invoke
def test_invoke_queued_delivers_string_named_slot(qapp) -> None:
    """PySide accepts string method names despite the current stub signature."""
    receiver = _Receiver()

    accepted = invoke_queued(receiver, "receive", Q_ARG(str, "delivered"))
    qapp.processEvents()

    assert accepted is True
    assert receiver.values == ["delivered"]
