"""Settings for the optional LanguageTool spelling capability."""

from typing import Optional, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

from src.gui.utils.help_context import declare_inspection


class SpellCheckSettingsDialog(QDialog):
    """Settings dialog for the LanguageTool spell/grammar check feature.

    Allows the user to opt in, choose a language, and optionally provide
    premium credentials for the LanguageTool public API.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the settings dialog.

        Args:
            parent: Optional parent widget.
        """
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import (
            QComboBox,
            QFormLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
        )

        from src.core.theme_manager import ThemeManager
        from src.gui.utils.style_helper import StyleHelper
        from src.gui.widgets.standard_buttons import (
            PrimaryButton,
            StandardButton,
            StandardCheckbox,
        )

        super().__init__(parent)
        self.setWindowTitle("Spell & Grammar Check")
        self.setMinimumWidth(400)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._apply_style()
        ThemeManager().theme_changed.connect(self._apply_style)

        layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(layout)

        # Enable toggle
        self._enabled_cb = StandardCheckbox("Enable spell & grammar checking")
        layout.addWidget(self._enabled_cb)

        # Language selector
        lang_group = QGroupBox("Language")
        lang_form = QFormLayout(lang_group)
        StyleHelper.apply_standard_list_spacing(lang_form)
        self._language_combo = declare_inspection(
            QComboBox(),
            "src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-self-language-combo|writing.spelling|help-inspect-src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-self-language-combo",
        )
        self._language_combo.setEditable(True)
        self._language_combo.addItems(
            ["auto", "en-US", "en-GB", "de-DE", "fr-FR", "es-ES", "pt-BR", "it-IT"]
        )
        self._language_combo.setStyleSheet(StyleHelper.get_input_field_style())
        lang_form.addRow("Language:", self._language_combo)
        layout.addWidget(lang_group)

        # Premium group
        premium_group = QGroupBox("Premium Account (optional)")
        premium_layout = QFormLayout(premium_group)
        StyleHelper.apply_standard_list_spacing(premium_layout)

        self._username_edit = declare_inspection(
            QLineEdit(),
            "src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-self-username-edit|writing.spelling|help-inspect-src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-self-username-edit",
        )
        self._username_edit.setPlaceholderText("your@email.com")
        self._username_edit.setStyleSheet(StyleHelper.get_input_field_style())
        premium_layout.addRow("Username:", self._username_edit)

        self._apikey_edit = declare_inspection(
            QLineEdit(),
            "src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-self-apikey-edit|writing.spelling|help-inspect-src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-self-apikey-edit",
        )
        self._apikey_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._apikey_edit.setPlaceholderText("API key")
        self._apikey_edit.setStyleSheet(StyleHelper.get_input_field_style())
        premium_layout.addRow("API Key:", self._apikey_edit)

        layout.addWidget(premium_group)

        # Info label
        info = QLabel(
            'Uses the <a href="https://languagetool.org">LanguageTool</a> public API. '
            "Free tier: 20 req/min, 20 KB/request."
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        layout.addWidget(info)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = declare_inspection(
            StandardButton("Cancel"),
            "src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-cancel-btn|writing.spelling|help-inspect-src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-cancel-btn",
        )
        cancel_btn.clicked.connect(self.close)
        save_btn = declare_inspection(
            PrimaryButton("Save"),
            "src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-save-btn|writing.spelling|help-inspect-src-gui-widgets-wiki-text-edit-spellchecksettingsdialog-init-save-btn",
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        # Load current settings
        s = QSettings()
        s.beginGroup("SpellCheck")
        self._enabled_cb.setChecked(cast(bool, s.value("enabled", False, type=bool)))
        lang = cast(str, s.value("language", "auto"))
        idx = self._language_combo.findText(lang)
        if idx >= 0:
            self._language_combo.setCurrentIndex(idx)
        else:
            self._language_combo.setCurrentText(lang)
        self._username_edit.setText(cast(str, s.value("username", "")))
        self._apikey_edit.setText(cast(str, s.value("api_key", "")))
        s.endGroup()

    def _apply_style(self) -> None:
        """Apply the current theme stylesheet to this dialog."""
        from src.gui.utils.style_helper import StyleHelper

        self.setStyleSheet(
            StyleHelper.get_dialog_base_style() + StyleHelper.get_scrollbar_style()
        )

    def _save(self) -> None:
        """Persist settings to QSettings and close the dialog."""
        from PySide6.QtCore import QSettings

        s = QSettings()
        s.beginGroup("SpellCheck")
        s.setValue("enabled", self._enabled_cb.isChecked())
        s.setValue("language", self._language_combo.currentText())
        s.setValue("username", self._username_edit.text())
        s.setValue("api_key", self._apikey_edit.text())
        s.endGroup()
        self.accept()
