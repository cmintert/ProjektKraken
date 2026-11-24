"""Own and publish the current world's authoring scope."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QDialog, QLabel, QWidget

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.core.authoring_scope import AuthoringScope
from src.gui.dialogs.authoring_scope_dialog import AuthoringScopeDialog
from src.gui.utils.help_context import declare_inspection
from src.gui.widgets.standard_buttons import StandardButton

logger = logging.getLogger(__name__)


class AuthoringScopeCoordinator(QObject):
    """Keep view scope, its revision, and its settings scoped to a world."""

    changed = Signal(object)

    def __init__(
        self, world_id: str, tags: Callable[[], list[str]], parent: QWidget
    ) -> None:
        """Restore the latest world expression and create its status action."""
        super().__init__(parent)
        self._parent = parent
        self._settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        self._key = f"worlds/{world_id}/authoring_scope"
        self._tags = tags
        self.revision = 0
        self.scope = self._restore()
        self.button = declare_inspection(
            StandardButton(),
            "authoring-scope|explorer.browsing|help-inspect-authoring-scope",
        )
        self.button.setAccessibleName("Authoring Scope")
        self.button.clicked.connect(self.edit)
        self.outside_scope = QLabel("Active item outside scope", parent)
        self.outside_scope.hide()
        self._update_label()

    def show_outside_scope(self, outside: bool) -> None:
        """Identify an active item that remains open outside the expression."""
        self.outside_scope.setVisible(outside)

    def _restore(self) -> AuthoringScope:
        try:
            raw = json.loads(str(self._settings.value(self._key, "{}")))
            if isinstance(raw, dict):
                return AuthoringScope.from_dict(raw)
        except ValueError:
            logger.warning("Ignoring malformed authoring scope")
        return AuthoringScope()

    def _update_label(self) -> None:
        tags = self.scope.tags
        caption = tags[0] if tags else "All Content"
        if len(tags) > 1:
            caption = f"{self.scope.mode.upper()} ({len(tags)} tags)"
        self.button.setText(f"Scope: {caption[:32]}")
        missing = sorted(set(tags).difference(self._tags()))
        tooltip = ", ".join(tags) or "All Content"
        if missing:
            tooltip += "\nMissing tags: " + ", ".join(missing)
        self.button.setToolTip(tooltip)

    def set_scope(self, scope: AuthoringScope) -> None:
        """Publish a new scope without changing any local filter."""
        if scope == self.scope:
            return
        self.scope = scope
        self.revision += 1
        self._settings.setValue(self._key, json.dumps(scope.to_dict()))
        self._update_label()
        self.changed.emit(scope)

    def tags_changed(self) -> None:
        """Refresh saved missing-tag diagnostics after catalog hydration."""
        self._update_label()

    def edit(self) -> None:
        """Open the keyboard-accessible scope editor."""
        dialog = AuthoringScopeDialog(self.scope, self._tags(), self._parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_scope(dialog.scope)
        dialog.deleteLater()
