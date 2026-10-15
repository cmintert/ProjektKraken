"""Bind explicit construction-site Help identities without UI-text inference."""

from __future__ import annotations

import shiboken6
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QToolButton,
    QWidget,
)

from src.gui.utils.help_context import HelpContextRegistry

_BINDING_PARTS = 3


def declared_binding(obj: QWidget | QAction) -> tuple[str, str, str] | None:
    """Read the reviewed semantic declaration retained by the native object."""
    if not shiboken6.isValid(obj):
        return None
    value = obj.property("krakenHelpBinding")
    if not isinstance(value, str):
        return None
    parts = value.split("|")
    return (parts[0], parts[1], parts[2]) if len(parts) == _BINDING_PARTS else None


def bind_declared_widget(registry: HelpContextRegistry, widget: QWidget) -> None:
    """Retain specialist registrations while adding ordinary control meanings."""
    value = declared_binding(widget)
    if value is not None and widget not in registry.inspection:
        registry.register_inspection(widget, *value)
    registration = registry.inspection.get(widget)
    parent = widget.parentWidget()
    if registration is not None and parent is not None:
        for form in parent.findChildren(QFormLayout):
            label = form.labelForField(widget)
            if isinstance(label, QLabel):
                registry.register_inspection(
                    label,
                    registration.meaning,
                    registration.topic_id,
                    registration.excerpt_target,
                )
    if value is not None and isinstance(widget, QDialogButtonBox):
        _bind_dialog_roles(registry, widget, value[1])
    if isinstance(widget, QToolButton) and widget.defaultAction() is not None:
        action = widget.defaultAction()
        bind_declared_action(registry, action, widget)
        resolved = registry.inspection_action(action)
        if resolved is not None:
            registration = resolved[1]
            registry.register_inspection(
                widget,
                registration.meaning,
                registration.topic_id,
                registration.excerpt_target,
            )
    if isinstance(widget, QMessageBox):
        parent = widget.parentWidget()
        candidates, _surface = registry.candidates(parent)
        topic = next(
            (candidate for candidate in candidates if candidate != "manual.home"), None
        )
        if topic is not None:
            _bind_message_roles(registry, widget, topic)


def _bind_message_roles(
    registry: HelpContextRegistry,
    box: QMessageBox,
    topic: str,
) -> None:
    roles = {
        QMessageBox.ButtonRole.AcceptRole: "accept",
        QMessageBox.ButtonRole.YesRole: "accept",
        QMessageBox.ButtonRole.RejectRole: "cancel",
        QMessageBox.ButtonRole.NoRole: "cancel",
        QMessageBox.ButtonRole.ApplyRole: "apply",
        QMessageBox.ButtonRole.DestructiveRole: "destructive",
        QMessageBox.ButtonRole.ResetRole: "reset",
        QMessageBox.ButtonRole.HelpRole: "help",
    }
    for button in box.buttons():
        if declared_binding(button) is not None:
            bind_declared_widget(registry, button)
            continue
        role = roles.get(box.buttonRole(button))
        if role is not None:
            registry.register_inspection(
                button, "dialog." + role, topic, "help-inspect-dialog-" + role
            )


def _bind_dialog_roles(
    registry: HelpContextRegistry,
    box: QDialogButtonBox,
    topic: str,
) -> None:
    roles = {
        QDialogButtonBox.ButtonRole.AcceptRole: "accept",
        QDialogButtonBox.ButtonRole.YesRole: "accept",
        QDialogButtonBox.ButtonRole.RejectRole: "cancel",
        QDialogButtonBox.ButtonRole.NoRole: "cancel",
        QDialogButtonBox.ButtonRole.ApplyRole: "apply",
        QDialogButtonBox.ButtonRole.DestructiveRole: "destructive",
        QDialogButtonBox.ButtonRole.ResetRole: "reset",
        QDialogButtonBox.ButtonRole.HelpRole: "help",
    }
    for button in box.buttons():
        role = roles.get(box.buttonRole(button))
        if role is not None:
            registry.register_inspection(
                button, "dialog." + role, topic, "help-inspect-dialog-" + role
            )


def bind_declared_action(
    registry: HelpContextRegistry,
    action: QAction,
    owner: QWidget,
) -> None:
    """Use a stable authoring owner for a transient menu's explanation links."""
    if not shiboken6.isValid(action):
        return
    registry.retain_inspection_action(action)
    while isinstance(owner, QMenu):
        parent = owner.parentWidget()
        if parent is None:
            break
        owner = parent
    value = declared_binding(action)
    equivalent = action.property("krakenHelpEquivalent")
    if isinstance(equivalent, QWidget):
        registration = registry.inspection.get(equivalent)
        if registration is not None:
            registry.register_inspection_action(
                action,
                registration.meaning,
                registration.topic_id,
                owner,
                registration.excerpt_target,
            )
            return
        value = declared_binding(equivalent) or value
    menu = action.menu()
    if isinstance(menu, QWidget):
        registry.retain_inspection_menu(menu)
    if value is None and isinstance(menu, QWidget):
        value = declared_binding(menu)
    if value is None:
        return
    registry.register_inspection_action(action, value[0], value[1], owner, value[2])
