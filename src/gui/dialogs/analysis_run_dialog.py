"""Explicit scope and request controls for AI Analysis Suite runs."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.analysis import AnalysisPreset, AnalysisScope, AnalysisScopeKind

_MINIMUM_MULTI_SELECTION_ITEMS = 2


class AnalysisRunDialog(QDialog):
    """Collect a valid explicit scope, categories, and request preset."""

    def __init__(
        self,
        current_item_id: str | None = None,
        selection_ids: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the analysis configuration dialog."""
        super().__init__(parent)
        self.setWindowTitle("Run AI Analysis")
        self.setMinimumWidth(520)
        self._current_item_id = current_item_id or ""
        self._selection_ids = selection_ids or []
        self._build_ui()
        self._update_validity()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Choose exactly what the AI may inspect. Results are advisory, "
                "session-only, and never modify world data."
            )
        )

        form = QFormLayout()
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Select a scope…", None)
        for label, kind in (
            ("Whole world", AnalysisScopeKind.WHOLE_WORLD),
            ("Current item", AnalysisScopeKind.CURRENT_ITEM),
            ("Multi-selection", AnalysisScopeKind.SELECTION),
            ("Any selected tag", AnalysisScopeKind.TAGS),
            ("Inclusive lore-date range", AnalysisScopeKind.DATE_RANGE),
        ):
            self.scope_combo.addItem(label, kind)
        form.addRow("Scope", self.scope_combo)

        self.selection_edit = QLineEdit(", ".join(self._selection_ids))
        self.selection_edit.setPlaceholderText("Object IDs separated by commas")
        form.addRow("Selection IDs", self.selection_edit)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Tags separated by commas")
        form.addRow("Tags", self.tags_edit)

        range_widget = QWidget()
        range_layout = QHBoxLayout(range_widget)
        range_layout.setContentsMargins(0, 0, 0, 0)
        self.start_date = self._date_spin()
        self.end_date = self._date_spin()
        range_layout.addWidget(self.start_date)
        range_layout.addWidget(QLabel("through"))
        range_layout.addWidget(self.end_date)
        form.addRow("Lore dates", range_widget)

        self.preset_combo = QComboBox()
        for preset in AnalysisPreset:
            self.preset_combo.addItem(preset.value.title(), preset)
        self.preset_combo.setCurrentIndex(1)
        form.addRow("Preset", self.preset_combo)
        layout.addLayout(form)

        category_layout = QHBoxLayout()
        self.plot_holes = QCheckBox("Plot Holes")
        self.relations = QCheckBox("Relation Gaps")
        self.lore = QCheckBox("Lore Suggestions")
        for checkbox in (self.plot_holes, self.relations, self.lore):
            checkbox.setChecked(True)
            category_layout.addWidget(checkbox)
        layout.addLayout(category_layout)

        self.coverage_label = QLabel()
        self.coverage_label.setWordWrap(True)
        layout.addWidget(self.coverage_label)
        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.scope_combo.currentIndexChanged.connect(self._update_validity)
        self.preset_combo.currentIndexChanged.connect(self._update_validity)
        for edit in (self.selection_edit, self.tags_edit):
            edit.textChanged.connect(self._update_validity)
        for spin in (self.start_date, self.end_date):
            spin.valueChanged.connect(self._update_validity)
        for checkbox in (self.plot_holes, self.relations, self.lore):
            checkbox.toggled.connect(self._update_validity)

    @staticmethod
    def _date_spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-1_000_000_000.0, 1_000_000_000.0)
        spin.setDecimals(6)
        return spin

    def _scope(self) -> AnalysisScope | None:
        kind = self.scope_combo.currentData(Qt.ItemDataRole.UserRole)
        if not isinstance(kind, AnalysisScopeKind):
            return None
        ids = [
            value.strip()
            for value in self.selection_edit.text().split(",")
            if value.strip()
        ]
        tags = [
            value.strip()
            for value in self.tags_edit.text().split(",")
            if value.strip()
        ]
        if kind == AnalysisScopeKind.CURRENT_ITEM:
            ids = [self._current_item_id] if self._current_item_id else []
        return AnalysisScope(
            kind=kind,
            item_ids=ids,
            tags=tags,
            start_date=self.start_date.value(),
            end_date=self.end_date.value(),
        )

    def _update_validity(self) -> None:
        scope = self._scope()
        reason = ""
        if scope is None:
            reason = "Select a scope before starting."
        elif scope.kind == AnalysisScopeKind.CURRENT_ITEM and not scope.item_ids:
            reason = "No current entity or event is selected."
        elif (
            scope.kind == AnalysisScopeKind.SELECTION
            and len(scope.item_ids) < _MINIMUM_MULTI_SELECTION_ITEMS
        ):
            reason = "Multi-selection requires at least two object IDs."
        elif scope.kind == AnalysisScopeKind.TAGS and not scope.tags:
            reason = "Select at least one tag."
        elif (
            scope.kind == AnalysisScopeKind.DATE_RANGE
            and scope.start_date is not None
            and scope.end_date is not None
            and scope.start_date > scope.end_date
        ):
            reason = "The start date must not be after the end date."
        categories = self.selected_categories()
        if not categories:
            reason = "Select at least one analysis category."
        preset = self.preset_combo.currentData(Qt.ItemDataRole.UserRole)
        if not isinstance(preset, AnalysisPreset):
            preset = AnalysisPreset.BALANCED
        maximum = sum(
            preset.limits[name]
            for name in categories
        )
        self.coverage_label.setText(
            "Eligible coverage is calculated from the captured scope before model "
            f"requests. Estimated initial requests: at most {maximum}; each malformed "
            "response may receive one disclosed repair request."
        )
        self.validation_label.setText(reason)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(not reason)

    def selected_categories(self) -> list[str]:
        """Return enabled analysis category identifiers."""
        return [
            name
            for name, checkbox in (
                ("plot_holes", self.plot_holes),
                ("relations", self.relations),
                ("lore", self.lore),
            )
            if checkbox.isChecked()
        ]

    def run_options(self) -> dict[str, Any]:
        """Return the validated, serializable run configuration."""
        scope = self._scope()
        if scope is None:
            raise ValueError("analysis scope is required")
        preset = self.preset_combo.currentData(Qt.ItemDataRole.UserRole)
        if not isinstance(preset, AnalysisPreset):
            preset = AnalysisPreset.BALANCED
        return {
            "scope": scope.to_dict(),
            "preset": preset.value,
            "analysis_types": self.selected_categories(),
        }
