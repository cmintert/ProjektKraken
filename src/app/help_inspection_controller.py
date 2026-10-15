"""Native control inspection without authoring gestures or prose in widgets."""

from __future__ import annotations

import html
import weakref
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtGui import (
    QCursor,
    QHelpEvent,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QWhatsThisClickedEvent,
)
from PySide6.QtWidgets import QApplication, QMenu, QMenuBar, QWhatsThis, QWidget

from src.app.help_declared_bindings import bind_declared_action, bind_declared_widget
from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import (
    ControlHelpRegistration,
    HelpContextRegistry,
    ancestors,
    help_focus_transfer,
)
from src.gui.utils.style_helper import StyleHelper
from src.services.help_bundle_service import HelpBundleError, HelpBundleService

if TYPE_CHECKING:
    from src.app.coordinators.help_coordinator import HelpCoordinator


class HelpInspectionController(QObject):
    """Handle Qt-native Help events and track their transient popup ownership."""

    def __init__(
        self,
        registry: HelpContextRegistry,
        service: HelpBundleService,
        help_coordinator: HelpCoordinator,
    ) -> None:
        """Bind one application-scoped controller to existing Help navigation."""
        super().__init__(help_coordinator)
        self.registry = registry
        self.service = service
        self.help = help_coordinator
        self.popup: weakref.ReferenceType[QWidget] | None = None
        self._mode = False
        self._stopped = False
        self._allow_restore = True
        self._pointer_request = False
        self.target: weakref.ReferenceType[QWidget] | None = None
        self._dismiss_key: int | None = None
        self._popup_token = 0
        self._next_popup_token = 0
        self._topic_id: str | None = None
        self._excerpt_target: str | None = None
        self._swallow_release = False
        ThemeManager().theme_changed.connect(self._theme_changed)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.installEventFilter(self)

    def enter(self) -> None:
        """Enter pointer targeting after preserving the authoring origin."""
        self.help.track_origin(None, QApplication.focusWidget())
        self.help.suspend_origin()
        self._mode = True
        self._pointer_request = True
        self._allow_restore = True
        QWhatsThis.enterWhatsThisMode()
        self._prioritize()

    def _prioritize(self) -> None:
        """Run input ownership before Qt's newly installed inspection filter."""
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.removeEventFilter(self)
            app.installEventFilter(self)

    def display(
        self, widget: QWidget, point: QPoint | None, global_point: QPoint
    ) -> bool:
        """Resolve and show only a reviewed, hash-checked canonical excerpt."""
        registration = self.registry.inspection_for(widget, point)
        if registration is None:
            return False
        return self._display_registration(registration, global_point)

    def _display_registration(
        self,
        registration: tuple[QWidget, ControlHelpRegistration],
        point: QPoint,
    ) -> bool:
        """Show validated content after resolving a control or menu action."""
        target, meaning = registration
        self.help.suspend_origin()
        self._allow_restore = True
        self.target = weakref.ref(target)
        self._topic_id = meaning.topic_id
        self._excerpt_target = meaning.excerpt_target
        text = self._explanation(meaning.topic_id, meaning.excerpt_target)
        with help_focus_transfer():
            QWhatsThis.leaveWhatsThisMode()
            for widget in QApplication.allWidgets():
                if isinstance(widget, QMenu) and widget.isVisible():
                    widget.hide()
            QWhatsThis.showText(point, text, target)
        self._track_popup()
        self._pointer_request = False
        return True

    def _explanation(self, topic_id: str, target: str | None = None) -> str:
        try:
            self.service.validate()
            excerpt = self.service.load_inspection_excerpt(topic_id, target)
            if not excerpt or not excerpt.strip():
                raise HelpBundleError(
                    "topic",
                    "This control explanation is unavailable.",
                    packaged=self.service.packaged,
                )
            style = StyleHelper.get_wiki_link_style()
            text = (
                f'<div style="{StyleHelper.get_read_only_text_style()}">'
                + excerpt
                + (
                    f'<p><a href="topic:{html.escape(topic_id)}" style="{style}">'
                    "Read the task in Help</a></p></div>"
                )
            )
        except HelpBundleError as exc:
            text = html.escape(str(exc))
        return text

    def _track_popup(self) -> None:
        popup = QApplication.activePopupWidget()
        if popup is not None:
            self._dismiss_key = None
            StyleHelper.apply_read_only_palette(popup)
            self._next_popup_token += 1
            self._popup_token = self._next_popup_token
            popup.setProperty("krakenInspectionToken", self._popup_token)
            popup.setProperty("krakenHelpInspectionPopup", True)
            handle = popup.windowHandle()
            if handle is not None:
                handle.setProperty("krakenHelpInspectionPopup", True)
            reference = weakref.ref(popup)
            self.popup = reference
            app = QApplication.instance()
            if app:
                app.setProperty("krakenInspectionPopup", True)
            popup.installEventFilter(self)
            token = self._popup_token
            popup.destroyed.connect(lambda: self._popup_closed(token))
            self._prioritize()
        else:
            self._popup_closed()

    def _active_popup(self) -> QWidget | None:
        # Qt owns the native object; its Python wrapper can be collected while
        # the C++ popup survives. Refresh the weak snapshot through Qt's API.
        popup = QApplication.activePopupWidget()
        if (
            popup is not None
            and popup.property("krakenInspectionToken") == self._popup_token
        ):
            self.popup = weakref.ref(popup)
            return popup
        return None

    def _theme_changed(self, _theme: dict[str, str]) -> None:
        popup = self._active_popup()
        target = self.help.live(self.target)
        if popup is None or target is None or self._topic_id is None:
            return
        point = popup.pos()
        with help_focus_transfer():
            QWhatsThis.showText(
                point, self._explanation(self._topic_id, self._excerpt_target), target
            )
        self._track_popup()

    def _popup_closed(self, token: int | None = None) -> None:
        if token is not None and token != self._popup_token:
            return
        self.popup = None
        self._popup_token = 0
        app = QApplication.instance()
        if app:
            app.setProperty("krakenInspectionPopup", False)
        if not self._stopped and self._allow_restore:
            QTimer.singleShot(0, self._restore_origin)

    def _restore_origin(self) -> None:
        if (
            not self._allow_restore
            or self._stopped
            or QWhatsThis.inWhatsThisMode()
            or self._active_popup()
        ):
            return
        origin = self.help.live(self.help.origin)
        if origin is not None and origin.isVisible():
            origin.setProperty("krakenHelpSuspendedOrigin", False)
            origin.setFocus(Qt.FocusReason.OtherFocusReason)

    def dismiss(self, *, restore: bool = True) -> None:
        """Leave local inspection before input can reach a draft or mode."""
        self._mode = False
        self._pointer_request = False
        self._allow_restore = restore
        self._dismiss_key = None
        QWhatsThis.leaveWhatsThisMode()
        QWhatsThis.hideText()
        self.popup = None
        app = QApplication.instance()
        if app:
            app.setProperty("krakenInspectionPopup", False)
        if restore:
            self._restore_origin()

    def stop(self) -> None:
        """Release filters and transient Qt windows without restoring focus."""
        self._stopped = True
        self.dismiss(restore=False)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.removeEventFilter(self)

    def _owner_teardown(self, watched: QObject, event: QEvent) -> None:
        if event.type() not in {QEvent.Type.Close, QEvent.Type.DeferredDelete}:
            return
        for reference in (self.help.origin, self.target):
            widget = self.help.live(reference)
            if widget and any(item is watched for item in ancestors(widget)):
                self.dismiss(restore=False)
                break

    def owner_closing(self, owner: QObject) -> None:
        """Dismiss before modal completion can dispose its target controls."""
        for reference in (self.help.origin, self.target):
            widget = self.help.live(reference)
            if widget is not None and any(item is owner for item in ancestors(widget)):
                self.dismiss(restore=False)
                return

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Use native What's This events rather than a Shift+F1 shortcut."""
        if self._stopped:
            return False
        if QWhatsThis.inWhatsThisMode() and event.type() in {
            QEvent.Type.Wheel,
            QEvent.Type.ContextMenu,
        }:
            return True
        if isinstance(event, QMouseEvent):
            handled = self._pointer_event(watched, event)
            if handled:
                return True
        popup = self._active_popup()
        if (
            popup is not None
            and isinstance(event, QKeyEvent)
            and (watched is popup or watched is popup.windowHandle())
        ):
            return self._popup_key(event)
        if (
            event.type() == QEvent.Type.Hide
            and isinstance(watched, QWidget)
            and watched.property("krakenInspectionToken") == self._popup_token
        ):
            self._popup_closed(self._popup_token)
        self._owner_teardown(watched, event)
        if not isinstance(watched, QWidget) or not self.help.belongs(watched):
            return False
        if event.type() == QEvent.Type.EnterWhatsThisMode:
            self.help.suspend_origin()
            self._mode = True
            self._pointer_request = True
        elif event.type() == QEvent.Type.LeaveWhatsThisMode:
            self._mode = False
            QTimer.singleShot(0, self._restore_origin)
        elif event.type() == QEvent.Type.QueryWhatsThis:
            point = (
                event.globalPos() if isinstance(event, QHelpEvent) else QCursor.pos()
            )
            registration = self._at_pointer(watched, point)
            event.setAccepted(registration is not None)
            return True
        elif isinstance(event, QHelpEvent) and event.type() == QEvent.Type.WhatsThis:
            local_point = (
                event.pos()
                if self._pointer_request or QWhatsThis.inWhatsThisMode()
                else None
            )
            registration = (
                self._at_pointer(watched, event.globalPos())
                if self._pointer_request or QWhatsThis.inWhatsThisMode()
                else None
            )
            event.setAccepted(
                self._display_registration(registration, event.globalPos())
                if registration
                else self.display(watched, local_point, event.globalPos())
            )
            return True
        elif isinstance(event, QWhatsThisClickedEvent):
            self._follow_task(event.href())
            return True
        elif isinstance(event, QKeyEvent):
            return self._native_key(watched, event)
        return False

    def _at_pointer(
        self,
        watched: QObject,
        point: QPoint,
    ) -> tuple[QWidget, ControlHelpRegistration] | None:
        """Resolve actual native hit targets, including disabled and menu items."""
        widget = QApplication.widgetAt(point)
        if widget is None and isinstance(watched, QWidget):
            widget = watched
        if widget is None or not self.help.belongs(widget):
            return None
        if isinstance(widget, (QMenu, QMenuBar)):
            action = widget.actionAt(widget.mapFromGlobal(point))
            if action is not None and not action.isSeparator():
                bind_declared_action(self.registry, action, widget)
                return self.registry.inspection_action(action)
            return None
        bind_declared_widget(self.registry, widget)
        return self.registry.inspection_for(widget, widget.mapFromGlobal(point))

    def _pointer_event(self, watched: QObject, event: QMouseEvent) -> bool:
        if self._swallow_release and event.type() == QEvent.Type.MouseButtonRelease:
            self._swallow_release = False
            return True
        if not QWhatsThis.inWhatsThisMode():
            return False
        point = event.globalPosition().toPoint()
        registration = self._at_pointer(watched, point)
        if event.type() == QEvent.Type.MouseMove:
            cursor = (
                Qt.CursorShape.WhatsThisCursor
                if registration
                else Qt.CursorShape.ForbiddenCursor
            )
            QApplication.changeOverrideCursor(QCursor(cursor))
            widget = QApplication.widgetAt(point)
            if isinstance(widget, (QMenu, QMenuBar)):
                action = widget.actionAt(widget.mapFromGlobal(point))
                if action is not None and action.menu() is not None:
                    menu = action.menu()
                    if isinstance(menu, QMenu) and not menu.isVisible():
                        menu.popup(
                            widget.mapToGlobal(
                                widget.actionGeometry(action).bottomLeft()
                            )
                        )
                return True
        if event.type() in {
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonDblClick,
        }:
            self._swallow_release = True
            if registration is not None and event.button() == Qt.MouseButton.LeftButton:
                self._display_registration(registration, point)
            return True
        return False

    def _follow_task(self, href: str) -> None:
        self.dismiss(restore=False)
        if not href.startswith("topic:"):
            return
        topic = href.removeprefix("topic:")
        try:
            if self.service.find_topic(topic) is not None:
                self.help.open_topic(topic)
        except HelpBundleError as exc:
            self.help.error(exc)
            self.help.show()

    def _popup_key(self, event: QKeyEvent) -> bool:
        """Consume the full chord before dismissing Qt's self-deleting popup."""
        event.accept()
        modifiers = {
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        }
        if event.type() == QEvent.Type.KeyPress and event.key() not in modifiers:
            self._dismiss_key = event.key()
        if event.type() == QEvent.Type.KeyRelease and self._dismiss_key is not None:
            if event.modifiers() == Qt.KeyboardModifier.NoModifier:
                self._dismiss_key = None
                QTimer.singleShot(0, self.dismiss)
        return True

    def _native_key(self, watched: QWidget, event: QKeyEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.matches(
            QKeySequence.StandardKey.WhatsThis
        ):
            registration = self.registry.inspection_for(watched)
            if registration:
                target, meaning = registration
                self.help.suspend_origin()
                self._allow_restore = True
                self.target = weakref.ref(target)
                self._topic_id = meaning.topic_id
                self._excerpt_target = meaning.excerpt_target
                target.setWhatsThis(
                    self._explanation(meaning.topic_id, meaning.excerpt_target)
                )
                app = QApplication.instance()
                if app:
                    app.setProperty("krakenInspectionPopup", True)
                QTimer.singleShot(0, self._track_popup)
            else:
                # A region may be exempt even when another item in its owning
                # view has an explanation. Never reuse that item's native text.
                event.accept()
                return True
            # Qt's native focused-control mechanism performs the display.
            return False
        if self._mode and event.key() == Qt.Key.Key_Escape:
            self.dismiss()
            return True
        return False
