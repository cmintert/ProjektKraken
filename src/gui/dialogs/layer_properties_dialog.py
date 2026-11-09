"""Contextual editor for persisted map-layer properties."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.map import VECTOR_LAYER_TYPES, MapLayerNode
from src.core.map_constants import MAP_LAYER_TYPE_GROUP
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.map.settings_scope import settings_scope, zoom_caption
from src.gui.widgets.numeric_inputs import ScrollSafeDoubleSpinBox
from src.gui.widgets.responsive_dialog_buttons import (
    ResponsiveDialogButtonBox as QDialogButtonBox,
)
from src.gui.widgets.wrapping_choices import WrappingCheckBox as QCheckBox


class LayerPropertiesDialog(QDialog):
    """Edit common and advanced properties without mutating the layer model."""

    def __init__(
        self,
        node: MapLayerNode,
        parent: Optional[QWidget] = None,
        *,
        root: MapLayerNode | None = None,
    ) -> None:
        """Initialize the layer-properties editor."""
        super().__init__(parent)
        self._node = deepcopy(node)
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        scope = settings_scope(node, root)
        self.setWindowTitle(scope.properties_label.removesuffix("…"))
        self.setMinimumWidth(420)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        layout = QVBoxLayout(self)
        self._scope_label = QLabel()
        self._scope_label.setTextFormat(Qt.TextFormat.PlainText)
        self._scope_label.setWordWrap(True)
        layout.addWidget(self._scope_label)
        self.set_scope(node, root)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._name = declare_inspection(
            QLineEdit(node.name),
            "src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-name|map.layers|help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-name",
        )
        self._visible = declare_inspection(
            QCheckBox("Visible"),
            "src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-visible|map.layers|help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-visible",
        )
        self._visible.setChecked(node.visible)
        self._opacity = declare_inspection(
            ScrollSafeDoubleSpinBox(),
            "src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-opacity|map.layers|help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-opacity",
        )
        self._opacity.setRange(0.0, 1.0)
        self._opacity.setSingleStep(0.05)
        self._opacity.setValue(node.opacity)
        self._notes = declare_inspection(
            QPlainTextEdit(str(node.attributes.get("notes", ""))),
            "src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-notes|map.layers|help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-notes",
        )
        self._notes.setMaximumHeight(90)
        form.addRow("Name in Layers:", self._name)
        form.addRow(self._visible)
        form.addRow("Opacity:", self._opacity)
        self._opacity_hint = QLabel()
        self._opacity_hint.setWordWrap(True)
        form.addRow(self._opacity_hint)
        form.addRow("Notes:", self._notes)

        self._exclusive = declare_inspection(
            QCheckBox("Only one child visible at a time"),
            "src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-exclusive|map.layers|help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-exclusive",
        )
        self._exclusive.setChecked(node.mutually_exclusive)
        self._exclusive.setVisible(node.layer_type == MAP_LAYER_TYPE_GROUP)
        form.addRow("Group:", self._exclusive)
        form.labelForField(self._exclusive).setVisible(
            node.layer_type == MAP_LAYER_TYPE_GROUP
        )

        self._min_zoom = declare_inspection(
            ScrollSafeDoubleSpinBox(),
            "src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-min-zoom|map.layers|help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-min-zoom",
        )
        self._min_zoom.setRange(0.0, max(100.0, node.min_zoom))
        self._min_zoom.setDecimals(2)
        self._min_zoom.setValue(float(node.min_zoom))
        self._max_zoom_enabled = declare_inspection(
            QCheckBox("Maximum zoom"),
            "src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-max-zoom-enabled|map.layers|help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-max-zoom-enabled",
        )
        self._max_zoom = declare_inspection(
            ScrollSafeDoubleSpinBox(),
            "src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-max-zoom|map.layers|help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-max-zoom",
        )
        self._max_zoom.setRange(
            0.0, max(100.0, node.max_zoom if node.max_zoom != float("inf") else 100.0)
        )
        self._max_zoom.setDecimals(2)
        finite_max = node.max_zoom != float("inf")
        self._max_zoom_enabled.setChecked(finite_max)
        self._max_zoom.setEnabled(finite_max)
        self._max_zoom.setValue(float(node.max_zoom) if finite_max else 100.0)
        self._max_zoom_enabled.toggled.connect(self._max_zoom.setEnabled)
        form.addRow("Visible at zoom levels — minimum:", self._min_zoom)
        form.addRow(self._max_zoom_enabled, self._max_zoom)
        layout.addLayout(form)

        hint = QLabel(
            f"Stored zoom visibility: {zoom_caption(node)}. "
            "Group zoom limits also apply. This does not change icon size. "
            + (f"Containing groups: {scope.zoom}" if scope.zoom else "")
        )
        hint.setWordWrap(True)
        self._zoom_hint = hint
        layout.addWidget(hint)
        buttons = declare_inspection(
            QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel
            ),
            "src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-buttons|map.layers|help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-buttons",
        )
        self._buttons = buttons
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._initial_zoom = (
            self._min_zoom.value(),
            self._max_zoom.value(),
            self._max_zoom_enabled.isChecked(),
        )
        self.set_scope(node, root)

        connect_theme(self, self._apply_theme)
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Refresh shared presentation without touching draft controls."""
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        for label in (self._opacity_hint, self._zoom_hint):
            label.setStyleSheet(StyleHelper.get_supporting_caption_style())
        self._notes.setStyleSheet(StyleHelper.get_text_area_style())

    def set_scope(self, node: MapLayerNode, root: MapLayerNode | None) -> None:
        """Refresh target context without replacing an editor draft."""
        scope = settings_scope(node, root)
        self._scope_label.setText(
            f"{scope.heading}\n{scope.description}\n{scope.location}\n"
            "Settings affect the map representation. Name in Layers changes "
            "the tree label only.\n"
            + (
                "The separate Rename action also updates the linked entry.\n"
                if node.layer_type in VECTOR_LAYER_TYPES
                else ""
            )
            + (f"Containing groups: {scope.visibility}" if scope.visibility else "")
        )
        if hasattr(self, "_opacity_hint"):
            self._opacity_hint.setText(
                "Group opacity multiplies this value. "
                + (f"Containing groups: {scope.opacity}" if scope.opacity else "")
            )
            self._zoom_hint.setText(
                f"Stored zoom visibility: {zoom_caption(node)}. "
                "Group zoom limits also apply. This does not change icon size. "
                + (f"Containing groups: {scope.zoom}" if scope.zoom else "")
            )

    def properties(self) -> dict[str, Any]:
        """Return validated values for ``UpdateLayerPropertiesCommand``."""
        properties = {
            "name": self._name.text().strip(),
            "visible": self._visible.isChecked(),
            "opacity": self._opacity.value(),
            "notes": self._notes.toPlainText(),
            "mutually_exclusive": self._exclusive.isChecked(),
        }
        if self._initial_zoom != (
            self._min_zoom.value(),
            self._max_zoom.value(),
            self._max_zoom_enabled.isChecked(),
        ):
            properties.update(
                {
                    "min_zoom": self._node.min_zoom
                    if self._min_zoom.value() == self._initial_zoom[0]
                    else self._min_zoom.value(),
                    "max_zoom": self._node.max_zoom
                    if (self._max_zoom.value(), self._max_zoom_enabled.isChecked())
                    == (self._initial_zoom[1], self._initial_zoom[2])
                    else self._max_zoom.value()
                    if self._max_zoom_enabled.isChecked()
                    else float("inf"),
                    "zoom_basis": self._node.attributes.get("zoom_basis"),
                }
            )
        return properties
