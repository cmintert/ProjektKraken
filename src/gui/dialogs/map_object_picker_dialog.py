"""Search-and-create dialog used when placing linked objects on maps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QKeyEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class MapObjectChoice:
    """A selected existing object or a lightweight creation request."""

    action: str
    object_id: str = ""
    object_type: str = ""
    name: str = ""
    entity_type: str = ""


class EntityQuickCaptureDialog(QDialog):
    """Capture the minimum data needed to create a typed entity."""

    DEFAULT_TYPES = ("Character", "Location", "Faction", "Item", "Concept")

    def __init__(
        self,
        parent: QWidget | None = None,
        entity_types: list[str] | None = None,
    ) -> None:
        """Initialize a minimal name-and-type capture form."""
        super().__init__(parent)
        self.setWindowTitle("New Entity")
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(self)
        self.name_edit.setObjectName("entityNameEdit")
        self.type_combo = QComboBox(self)
        self.type_combo.setObjectName("entityTypeCombo")
        self.type_combo.setEditable(True)

        types = sorted(
            {
                item.strip()
                for item in [*self.DEFAULT_TYPES, *(entity_types or [])]
                if item.strip()
            },
            key=str.casefold,
        )
        self.type_combo.addItems(types)
        self.type_combo.setCurrentText("Concept")
        form.addRow("Name:", self.name_edit)
        form.addRow("Type:", self.type_combo)
        layout.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.name_edit.textChanged.connect(self._update_accept_enabled)
        self.type_combo.currentTextChanged.connect(self._update_accept_enabled)
        self._update_accept_enabled()

    def _update_accept_enabled(self) -> None:
        button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        button.setEnabled(bool(self.name() and self.entity_type()))

    def name(self) -> str:
        """Return the trimmed entity name."""
        return self.name_edit.text().strip()

    def entity_type(self) -> str:
        """Return the chosen or custom entity type."""
        return self.type_combo.currentText().strip()


class MapObjectPickerDialog(QDialog):
    """Show map creation actions and searchable existing objects together."""

    def __init__(
        self,
        entities: list[Any],
        events: list[Any],
        parent: QWidget | None = None,
        title: str = "Add Marker Here",
    ) -> None:
        """Initialize the picker from GUI-thread entity/event snapshots."""
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(440, 420)
        self._choice: MapObjectChoice | None = None
        self._entities = entities

        layout = QVBoxLayout(self)
        heading = QLabel(title, self)
        heading.setObjectName("mapObjectPickerHeading")
        layout.addWidget(heading)

        self.search_edit = QLineEdit(self)
        self.search_edit.setObjectName("mapObjectSearchEdit")
        self.search_edit.setPlaceholderText("Search existing objects…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.installEventFilter(self)
        layout.addWidget(self.search_edit)

        actions = QHBoxLayout()
        self.new_location_button = QPushButton("+ New Location", self)
        self.new_location_button.setObjectName("newLocationButton")
        self.new_entity_button = QPushButton("+ New Entity…", self)
        self.new_entity_button.setObjectName("newEntityButton")
        self.new_event_button = QPushButton("+ New Event", self)
        self.new_event_button.setObjectName("newEventButton")
        for button in (
            self.new_location_button,
            self.new_entity_button,
            self.new_event_button,
        ):
            actions.addWidget(button)
        layout.addLayout(actions)

        self.results_list = QListWidget(self)
        self.results_list.setObjectName("mapObjectResultsList")
        self.results_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        layout.addWidget(self.results_list)

        self.cancel_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        self.cancel_buttons.rejected.connect(self.reject)
        layout.addWidget(self.cancel_buttons)

        self._populate(entities, events)
        self.search_edit.textChanged.connect(self._filter_results)
        self.results_list.itemActivated.connect(self._accept_existing)
        self.results_list.itemDoubleClicked.connect(self._accept_existing)
        self.new_location_button.clicked.connect(self._capture_location)
        self.new_entity_button.clicked.connect(self._capture_entity)
        self.new_event_button.clicked.connect(self._capture_event)
        self.search_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def showEvent(self, event: QShowEvent) -> None:
        """Focus search as soon as the native dialog is shown."""
        super().showEvent(event)
        QTimer.singleShot(
            0,
            lambda: self.search_edit.setFocus(
                Qt.FocusReason.PopupFocusReason
            ),
        )

    def _populate(self, entities: list[Any], events: list[Any]) -> None:
        entries: list[tuple[str, str, str, str]] = []
        for entity in entities:
            entries.append(
                (
                    str(entity.name),
                    str(getattr(entity, "type", "Entity")),
                    str(entity.id),
                    "entity",
                )
            )
        for event in events:
            entries.append((str(event.name), "Event", str(event.id), "event"))

        for name, display_type, object_id, object_type in sorted(
            entries, key=lambda entry: (entry[0].casefold(), entry[1].casefold())
        ):
            item = QListWidgetItem(f"{name} · {display_type}")
            item.setData(
                Qt.ItemDataRole.UserRole,
                MapObjectChoice(
                    action="existing",
                    object_id=object_id,
                    object_type=object_type,
                    name=name,
                ),
            )
            item.setData(
                Qt.ItemDataRole.UserRole + 1,
                f"{name} {display_type}".casefold(),
            )
            self.results_list.addItem(item)
        if self.results_list.count():
            self.results_list.setCurrentRow(0)

    def _filter_results(self, text: str) -> None:
        needle = text.strip().casefold()
        first_visible = -1
        for row in range(self.results_list.count()):
            item = self.results_list.item(row)
            hidden = needle not in str(
                item.data(Qt.ItemDataRole.UserRole + 1)
            )
            item.setHidden(hidden)
            if not hidden and first_visible < 0:
                first_visible = row
        self.results_list.setCurrentRow(first_visible)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Support list navigation without moving focus away from search."""
        if watched is self.search_edit and event.type() == QEvent.Type.KeyPress:
            key_event = event
            if isinstance(key_event, QKeyEvent):
                if key_event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                    self._move_selection(1 if key_event.key() == Qt.Key.Key_Down else -1)
                    return True
                if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    item = self.results_list.currentItem()
                    if item is not None and not item.isHidden():
                        self._accept_existing(item)
                    return True
        return super().eventFilter(watched, event)

    def _move_selection(self, step: int) -> None:
        count = self.results_list.count()
        if not count:
            return
        row = self.results_list.currentRow()
        for offset in range(1, count + 1):
            candidate = (row + step * offset) % count
            if not self.results_list.item(candidate).isHidden():
                self.results_list.setCurrentRow(candidate)
                return

    def _accept_existing(self, item: QListWidgetItem) -> None:
        choice = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(choice, MapObjectChoice):
            self._choice = choice
            self.accept()

    def _capture_location(self) -> None:
        name, ok = QInputDialog.getText(self, "New Location", "Location Name:")
        if ok and name.strip():
            self._choice = MapObjectChoice(
                action="create",
                object_type="entity",
                name=name.strip(),
                entity_type="Location",
            )
            self.accept()

    def _capture_entity(self) -> None:
        entity_types = [
            str(getattr(entity, "type", "")).strip() for entity in self._entities
        ]
        dialog = EntityQuickCaptureDialog(self, entity_types)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._choice = MapObjectChoice(
                action="create",
                object_type="entity",
                name=dialog.name(),
                entity_type=dialog.entity_type(),
            )
            self.accept()

    def _capture_event(self) -> None:
        name, ok = QInputDialog.getText(self, "New Event", "Event Name:")
        if ok and name.strip():
            self._choice = MapObjectChoice(
                action="create", object_type="event", name=name.strip()
            )
            self.accept()

    def choice(self) -> MapObjectChoice | None:
        """Return the choice made before the dialog was accepted."""
        return self._choice
