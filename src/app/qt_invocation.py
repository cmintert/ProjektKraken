"""Typed helpers for invoking Qt slots across thread boundaries."""

from typing import Any

from PySide6.QtCore import QMetaObject, QObject, Qt


def invoke_method(
    target: QObject,
    method_name: str,
    connection_type: Qt.ConnectionType,
    *arguments: Any,
) -> bool:
    """Invoke a Qt slot using the requested connection type.

    PySide6 accepts a Python ``str`` method name at runtime, while its type stubs
    currently model this overload as accepting a bytes-like value. Keeping that
    mismatch in this verified boundary avoids scattering ignores across every
    coordinator.

    Args:
        target: QObject that owns the destination slot.
        method_name: Name of the Qt slot to invoke.
        connection_type: Qt delivery semantics to preserve.
        *arguments: Values produced by :func:`PySide6.QtCore.Q_ARG`.

    Returns:
        Whether Qt accepted the invocation.

    """
    return QMetaObject.invokeMethod(  # type: ignore[call-overload]
        target,
        method_name,
        connection_type,
        *arguments,
    )


def invoke_queued(target: QObject, method_name: str, *arguments: Any) -> bool:
    """Queue a slot invocation for delivery on the target object's thread.

    Args:
        target: QObject that owns the destination slot.
        method_name: Name of the Qt slot to invoke.
        *arguments: Values produced by :func:`PySide6.QtCore.Q_ARG`.

    Returns:
        Whether Qt accepted the invocation.

    """
    return invoke_method(
        target,
        method_name,
        Qt.ConnectionType.QueuedConnection,
        *arguments,
    )
