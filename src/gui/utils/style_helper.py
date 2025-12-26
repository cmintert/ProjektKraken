"""
Style Helper Module.

Provides centralized, theme-aware styling methods that use ThemeManager
tokens to generate consistent QSS strings. This eliminates hardcoded
colors and ensures theme switches reliably update the UI.
"""

from PySide6.QtWidgets import QLayout


class StyleHelper:
    """
    Centralized style helper that provides theme-aware QSS strings.

    All methods use ThemeManager.get_theme() to fetch current theme
    tokens and return formatted QSS strings that adapt to theme changes.
    """

    @staticmethod
    def get_empty_state_style() -> str:
        """
        Returns QSS for empty state labels.

        Empty state labels are shown when no data is available
        (e.g., "No Events Loaded").
        Uses text_dim color and appropriate font size.

        Returns:
            str: QSS stylesheet string for empty state labels.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return f"color: {theme['text_dim']}; font-size: 14pt;"

    @staticmethod
    def get_preview_label_style() -> str:
        """
        Returns QSS for preview labels.

        Preview labels show contextual information (e.g., formatted dates).
        Uses text_dim color and italic style.

        Returns:
            str: QSS stylesheet string for preview labels.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return f"color: {theme['text_dim']}; font-style: italic;"

    @staticmethod
    def get_error_label_style() -> str:
        """
        Returns QSS for error labels.

        Error labels display validation errors and warnings.
        Uses error color and bold font weight.

        Returns:
            str: QSS stylesheet string for error labels.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return f"color: {theme['error']}; font-weight: bold;"

    @staticmethod
    def get_section_header_style() -> str:
        """
        Returns QSS for section headers.

        Section headers are bold labels that divide content sections.

        Returns:
            str: QSS stylesheet string for section headers.
        """
        return "font-weight: bold;"

    @staticmethod
    def get_frame_style() -> str:
        """
        Returns QSS for standard frames.

        Standard frames provide visual separation with border and padding.
        Uses border color from theme.

        Returns:
            str: QSS stylesheet string for frames.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return (
            f"QFrame {{ border: 1px solid {theme['border']}; "
            f"border-radius: 3px; padding: 2px; }}"
        )

    @staticmethod
    def get_lore_frame_style() -> str:
        """
        Returns QSS for lore/narrative frames.

        Lore frames use accent_secondary color for left border to create
        an immersive visual distinction for narrative content.

        Returns:
            str: QSS stylesheet string for lore frames.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return (
            f"QFrame#LoreFrame {{ background-color: {theme['surface']}; "
            f"border: 1px solid {theme['border']}; "
            f"border-left: 4px solid {theme['accent_secondary']}; "
            f"border-radius: 4px; }}"
        )

    @staticmethod
    def get_map_viewport_style() -> str:
        """
        Returns QSS for map viewport frames.

        Map viewports use primary color border for technical/map content.

        Returns:
            str: QSS stylesheet string for map viewports.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return (
            f"QFrame#MapViewport {{ border: 2px solid {theme['primary']}; "
            f"background-color: #000000; }}"
        )

    @staticmethod
    def get_primary_button_style() -> str:
        """
        Returns QSS for primary action buttons.

        Primary buttons use the primary theme color and stand out.

        Returns:
            str: QSS stylesheet string for primary buttons.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return (
            f"QPushButton {{ background-color: {theme['primary']}; "
            f"color: #121212; border: 1px solid {theme['primary']}; "
            f"border-radius: 4px; padding: 6px 16px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {theme['border']}; "
            f"color: {theme['text_main']}; }}"
            f"QPushButton:pressed {{ background-color: {theme['surface']}; }}"
        )

    @staticmethod
    def get_destructive_button_style() -> str:
        """
        Returns QSS for destructive action buttons.

        Destructive buttons (delete, remove) use error color.

        Returns:
            str: QSS stylesheet string for destructive buttons.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return (
            f"QPushButton {{ background-color: {theme['error']}; "
            f"color: white; border: 1px solid {theme['error']}; "
            f"border-radius: 4px; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background-color: {theme['border']}; "
            f"color: {theme['text_main']}; }}"
        )

    @staticmethod
    def get_dialog_button_style(selected: bool) -> str:
        """
        Returns QSS for dialog day buttons.

        Used in calendar picker dialogs for day selection buttons.

        Args:
            selected: Whether this is the selected button style.

        Returns:
            str: QSS stylesheet string for dialog buttons.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()

        if selected:
            return (
                f"QPushButton#day_btn_selected {{ "
                f"background-color: {theme['primary']}; "
                f"color: white; font-weight: bold; "
                f"border: 1px solid {theme['primary']}; }}"
            )
        else:
            return (
                f'QPushButton[objectName^="day_btn"] {{ '
                f"background-color: {theme['border']}; "
                f"color: {theme['text_main']}; "
                f"border: 1px solid {theme['border']}; "
                f"padding: 0px; min-height: 0px; "
                f"font-size: 10pt; }}"
                f'QPushButton[objectName^="day_btn"]:hover {{ '
                f"background-color: {theme['surface']}; }}"
            )

    @staticmethod
    def get_dialog_base_style() -> str:
        """
        Returns base QSS for dialogs.

        Provides consistent dialog background and text colors.

        Returns:
            str: QSS stylesheet string for dialog base.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return (
            f"QDialog {{ background-color: {theme['app_bg']}; "
            f"color: {theme['text_main']}; }}"
        )

    @staticmethod
    def get_scrollbar_style() -> str:
        """
        Returns QSS for custom scrollbars.

        Provides themed scrollbar styling matching the current theme.

        Returns:
            str: QSS stylesheet string for scrollbars.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return (
            f"QScrollBar:vertical {{ "
            f"background-color: {theme['scrollbar_bg']}; "
            f"width: 10px; margin: 0px; }}"
            f"QScrollBar::handle:vertical {{ "
            f"background-color: {theme['scrollbar_handle']}; "
            f"min-height: 20px; border-radius: 5px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ "
            f"height: 0px; }}"
            f"QScrollBar:horizontal {{ "
            f"background-color: {theme['scrollbar_bg']}; "
            f"height: 10px; margin: 0px; }}"
            f"QScrollBar::handle:horizontal {{ "
            f"background-color: {theme['scrollbar_handle']}; "
            f"min-width: 20px; border-radius: 5px; }}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ "
            f"width: 0px; }}"
        )

    @staticmethod
    def get_wiki_link_style(broken: bool = False) -> str:
        """
        Returns QSS for wiki links.

        Wiki links are styled differently based on whether they're broken
        (target doesn't exist) or valid.

        Args:
            broken: Whether this is a broken link style.

        Returns:
            str: QSS stylesheet string for wiki links.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()

        if broken:
            return f"color: {theme['error']}; text-decoration: underline dotted;"
        else:
            return f"color: {theme['accent_secondary']}; text-decoration: underline;"

    @staticmethod
    def get_timeline_header_style() -> str:
        """
        Returns QSS for timeline headers.

        Timeline headers use surface background with border.

        Returns:
            str: QSS stylesheet string for timeline headers.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return (
            f"background-color: {theme['surface']}; "
            f"border-bottom: 1px solid {theme['border']}; "
            f"padding: 8px; font-weight: bold;"
        )

    @staticmethod
    def apply_standard_list_spacing(layout: QLayout) -> None:
        """
        Applies standard spacing for list layouts.

        Standard list spacing: 8px spacing, 16px margins (8-point grid).

        Args:
            layout: The QLayout to configure.
        """
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

    @staticmethod
    def apply_compact_spacing(layout: QLayout) -> None:
        """
        Applies compact spacing for dense layouts.

        Compact spacing: 4px spacing, 8px margins.

        Args:
            layout: The QLayout to configure.
        """
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)

    @staticmethod
    def apply_form_spacing(layout: QLayout) -> None:
        """
        Applies form spacing for form layouts.

        Form spacing: 8px spacing, 12px margins.

        Args:
            layout: The QLayout to configure.
        """
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

    @staticmethod
    def apply_no_margins(layout: QLayout) -> None:
        """
        Removes margins from a layout.

        Useful for nested layouts or widgets that need edge-to-edge content.

        Args:
            layout: The QLayout to configure.
        """
        layout.setContentsMargins(0, 0, 0, 0)

    @staticmethod
    def get_input_field_style() -> str:
        """
        Returns QSS for input fields (QLineEdit, QTextEdit).

        Provides consistent rounded corners and border styling.

        Returns:
            str: QSS stylesheet string for input fields.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        return (
            f"border: 1px solid {theme['border']}; "
            f"border-radius: 6px; "  # High rounded corners as requested
            f"background-color: {theme['surface']}; "
            f"color: {theme['text_main']}; "
            f"padding: 4px;"
        )
