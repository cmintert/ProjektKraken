"""Style Helper Module.

Provides centralized, theme-aware styling methods that use ThemeManager tokens to
generate consistent QSS strings. This eliminates hardcoded colors and ensures theme
switches reliably update the UI.
"""

import logging
from typing import Any, Optional, Tuple

from PySide6.QtCore import QEvent, QObject, QRect
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QLayout,
    QProxyStyle,
    QStyle,
    QToolTip,
    QWidget,
)

from src.app.constants import (
    TOOLTIP_DELAY_MS,
    TOOLTIP_DURATION_MS,
)
from src.core.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class TooltipProxyStyle(QProxyStyle):
    """Custom style to override tooltip delays."""

    def styleHint(
        self,
        hint: QStyle.StyleHint,
        option: Optional[Any] = None,
        widget: Optional[QWidget] = None,
        returnData: Optional[Any] = None,
    ) -> int:
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return TOOLTIP_DELAY_MS
        return super().styleHint(hint, option, widget, returnData)


class TooltipEventFilter(QObject):
    """Event filter to override tooltip duration globally."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.ToolTip:
            if isinstance(obj, QWidget):
                tooltip = obj.toolTip()
                if tooltip:
                    QToolTip.showText(
                        QCursor.pos(), tooltip, obj, QRect(), TOOLTIP_DURATION_MS
                    )
                    return True
        return super().eventFilter(obj, event)


class StyleHelper:
    """Centralized style helper that provides theme-aware QSS strings.

    All methods use ThemeManager.get_theme() to fetch current theme tokens and return
    formatted QSS strings that adapt to theme changes.
    """

    @staticmethod
    def get_empty_state_style() -> str:
        """Returns QSS for empty state labels.

        Empty state labels are shown when no data is available
        (e.g., "No Events Loaded").
        Uses text_dim color and appropriate font size.

        Returns:
            str: QSS stylesheet string for empty state labels.

        """

        theme = ThemeManager().get_theme()
        return f"color: {theme['text_dim']}; font-size: 14pt;"

    @staticmethod
    def get_preview_label_style() -> str:
        """Returns QSS for preview labels.

        Preview labels show contextual information (e.g., formatted dates).
        Uses text_dim color and italic style.

        Returns:
            str: QSS stylesheet string for preview labels.

        """

        theme = ThemeManager().get_theme()
        return f"color: {theme['text_dim']}; font-style: italic;"

    @staticmethod
    def get_error_label_style() -> str:
        """Returns QSS for error labels.

        Error labels display validation errors and warnings.
        Uses error color and bold font weight.

        Returns:
            str: QSS stylesheet string for error labels.

        """

        theme = ThemeManager().get_theme()
        return f"color: {theme['error']}; font-weight: bold;"

    @staticmethod
    def get_section_header_style() -> str:
        """Returns QSS for section headers.

        Section headers are bold labels that divide content sections.

        Returns:
            str: QSS stylesheet string for section headers.

        """
        return "font-weight: bold;"

    @staticmethod
    def get_frame_style() -> str:
        """Returns QSS for standard frames.

        Standard frames provide visual separation with border and padding.
        Uses border color from theme.

        Returns:
            str: QSS stylesheet string for frames.

        """

        theme = ThemeManager().get_theme()
        return (
            f"QFrame {{ border: 1px solid {theme['border']}; "
            f"border-radius: 3px; padding: 2px; }}"
        )

    # -------------------------------------------------------------------------
    # Sheet Builder Specific Styles
    # -------------------------------------------------------------------------

    @staticmethod
    def get_sheet_attribute_style() -> str:
        """Returns QSS for AttributePairWidget and GhostWidget in Sheet Builder.

        Returns:
            str: QSS stylesheet string.
        """
        theme = ThemeManager().get_theme()
        surface_alt = theme.get("surface_alt", "#2A2A2A")
        border = theme.get("border", "#333333")
        primary = theme.get("primary", "#5C82FF")

        return f"""
            AttributePairWidget {{
                background-color: {surface_alt};
                border: 1px solid {border};
                border-radius: 4px;
            }}
            AttributePairWidget:hover {{
                border: 1px solid {primary};
            }}
            AttributePairWidget QTextEdit {{
                background-color: transparent;
                border: none;
            }}
        """

    @staticmethod
    def get_sheet_text_block_style() -> str:
        """Returns QSS for TextBlockWidget in Sheet Builder.

        Returns:
            str: QSS stylesheet string.
        """
        theme = ThemeManager().get_theme()
        text_dim = theme.get("text_dim", "#808080")
        text = theme.get("text", "#E0E0E0")
        primary = theme.get("primary", "#5C82FF")

        return f"""
            TextBlockWidget {{
                border: 1px solid transparent;
                border-radius: 4px;
            }}
            TextBlockWidget:hover {{
                border: 1px solid {primary};
            }}
            TextBlockWidget QLineEdit {{
                background-color: transparent;
                border: none;
                color: {text_dim};
                font-style: italic;
                padding: 4px;
            }}
            TextBlockWidget QLineEdit:focus {{
                color: {text};
            }}
        """

    @staticmethod
    def get_sheet_divider_style() -> str:
        """Returns QSS for DividerWidget in Sheet Builder.

        Returns:
            str: QSS stylesheet string.
        """
        theme = ThemeManager().get_theme()
        border = theme.get("border", "#333333")
        primary = theme.get("primary", "#5C82FF")

        return f"""
            DividerWidget {{
                color: {border};
                background-color: {border};
            }}
            DividerWidget:hover {{
                color: {primary};
                background-color: {primary};
            }}
        """

    @staticmethod
    def get_sheet_spacer_style() -> str:
        """Returns QSS for SpacerWidget in Sheet Builder.

        Returns:
            str: QSS stylesheet string.
        """
        theme = ThemeManager().get_theme()
        border = theme.get("border", "#333333")
        primary = theme.get("primary", "#5C82FF")

        return f"""
            SpacerWidget {{
                background-color: transparent;
                border: 1px dashed {border};
                border-radius: 4px;
            }}
            SpacerWidget:hover {{
                border: 1px dashed {primary};
            }}
        """

    # -------------------------------------------------------------------------
    # Editor Specific Styles
    # -------------------------------------------------------------------------

    @staticmethod
    def get_editor_toolbar_style() -> str:
        """Returns QSS for the WikiTextEdit toolbar.

        Returns:
            str: QSS stylesheet string.
        """
        theme = ThemeManager().get_theme()
        surface = theme.get("surface", "#1A1A1A")
        border = theme.get("border", "#333333")
        primary = theme.get("primary", "#5C82FF")
        text = theme.get("text", "#E0E0E0")
        surface_alt = theme.get("surface_alt", "#2A2A2A")

        return f"""
            QToolBar {{
                background-color: {surface};
                border-bottom: 1px solid {border};
                border-top: none;
                border-left: none;
                border-right: none;
                spacing: 4px;
                padding: 2px;
            }}
            QToolButton {{
                background-color: transparent;
                color: {text};
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QToolButton:hover {{
                background-color: {surface_alt};
                border: 1px solid {border};
            }}
            QToolButton:pressed {{
                background-color: {primary};
        """

    @staticmethod
    def get_sheet_resize_handle_style() -> str:
        """Returns QSS for _ResizeHandle in Sheet Builder.

        Returns:
            str: QSS stylesheet string.
        """
        theme = ThemeManager().get_theme()
        primary = theme.get("primary", "#5C82FF")

        return f"""
            _ResizeHandle {{
                background-color: transparent;
            }}
            _ResizeHandle:hover {{
                background-color: {primary};
                border-radius: 2px;
            }}
        """

    @staticmethod
    def get_lore_frame_style() -> str:
        """Returns QSS for lore/narrative frames.

        Lore frames use accent_secondary color for left border to create
        an immersive visual distinction for narrative content.

        Returns:
            str: QSS stylesheet string for lore frames.

        """

        theme = ThemeManager().get_theme()
        return (
            f"QFrame#LoreFrame {{ background-color: {theme['surface']}; "
            f"border: 1px solid {theme['border']}; "
            f"border-left: 4px solid {theme['accent_secondary']}; "
            f"border-radius: 4px; }}"
        )

    @staticmethod
    def get_map_viewport_style() -> str:
        """Returns QSS for map viewport frames.

        Map viewports use primary color border for technical/map content.

        Returns:
            str: QSS stylesheet string for map viewports.

        """

        theme = ThemeManager().get_theme()
        return (
            f"QFrame#MapViewport {{ border: 2px solid {theme['primary']}; "
            f"background-color: #000000; }}"
        )

    @staticmethod
    def get_primary_button_style() -> str:
        """Returns QSS for primary action buttons.

        Primary buttons use the primary theme color and stand out.

        Returns:
            str: QSS stylesheet string for primary buttons.

        """

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
    def get_secondary_button_style() -> str:
        """Returns QSS for secondary (ghost) action buttons.

        Secondary buttons use a transparent background with a subtle border,
        suitable for less prominent actions alongside primary buttons.

        Returns:
            str: QSS stylesheet string for secondary buttons.

        """

        theme = ThemeManager().get_theme()
        return (
            f"QPushButton {{ background-color: transparent; "
            f"color: {theme['text_main']}; border: 1px solid {theme['border']}; "
            f"border-radius: 4px; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background-color: {theme['surface']}; }}"
            f"QPushButton:pressed {{ background-color: {theme['border']}; }}"
        )

    @staticmethod
    def get_tool_button_style() -> str:
        """
        Style sheet for tool and secondary action buttons targeting QToolButton and QPushButton.

        The style uses the theme's surface, text, border, primary, and app background colors and defines base, hover, pressed, and checked states.

        Returns:
            str: QSS stylesheet string for tool and secondary action buttons.
        """

        theme = ThemeManager().get_theme()
        return (
            f"QToolButton, QPushButton {{ background-color: {theme['surface']}; "
            f"color: {theme['text_main']}; border: 1px solid {theme['border']}; "
            f"border-radius: 4px; padding: 4px; }}"
            f"QToolButton:hover, QPushButton:hover {{ "
            f"background-color: {theme['border']}; }}"
            f"QToolButton:pressed, QPushButton:pressed {{ "
            f"background-color: {theme['app_bg']}; }}"
            f"QToolButton:checked, QPushButton:checked {{ "
            f"background-color: {theme['border']}; "
            f"border: 1px solid {theme['primary']}; }}"
        )

    @staticmethod
    def get_raster_tool_button_style() -> str:
        """Style for raster editing tool buttons with prominent checked state.

        Uses a highlighted primary background and contrasting border when
        checked so the active tool/mode is immediately obvious.

        Returns:
            str: QSS stylesheet string for raster tool buttons.
        """
        theme = ThemeManager().get_theme()
        primary = theme.get("primary", "#5C82FF")
        surface = theme.get("surface", "#1E1E1E")
        text_main = theme.get("text_main", "#E0E0E0")
        border = theme.get("border", "#333333")
        app_bg = theme.get("app_bg", "#121212")

        return (
            f"QPushButton {{ background-color: {surface}; "
            f"color: {text_main}; border: 1px solid {border}; "
            f"border-radius: 4px; padding: 4px 8px; font-size: 11px; }}"
            f"QPushButton:hover {{ background-color: {border}; }}"
            f"QPushButton:pressed {{ background-color: {app_bg}; }}"
            f"QPushButton:checked {{ "
            f"background-color: {primary}; color: {theme.get('text_on_primary', '#FFFFFF')}; "
            f"border: 2px solid {primary}; font-weight: bold; }}"
        )

    @staticmethod
    def get_flat_tool_button_style() -> str:
        """
        Returns QSS for flat tool buttons typically used in headers or toolbars.

        These buttons are transparent by default and only show a background on hover/press.
        """
        theme = ThemeManager().get_theme()
        text_dim = theme.get("text_dim", "#808080")
        text_main = theme.get("text_main", "#E0E0E0")
        border = theme.get("border", "#333333")
        primary = theme.get("primary", "#5C82FF")

        return (
            f"QToolButton {{ color: {text_dim}; background-color: transparent; "
            f"border: 1px solid transparent; border-radius: 3px; "
            f"padding: 3px 8px; font-size: 11px; }}"
            f"QToolButton:hover {{ color: {text_main}; "
            f"background-color: {border}; border: 1px solid {border}; }}"
            f"QToolButton:pressed {{ background-color: {primary}; color: white; }}"
        )

    @staticmethod
    def get_destructive_button_style() -> str:
        """
        Provide QSS for destructive action buttons using the theme's destructive color.

        Styles normal, hover, and disabled states for QPushButton to ensure consistent destructive button appearance.

        Returns:
            str: QSS stylesheet string for destructive action buttons.
        """

        theme = ThemeManager().get_theme()
        return (
            f"QPushButton {{ background-color: {theme['surface']}; "
            f"color: {theme['destructive']}; border: 1px solid {theme['destructive']}; "
            f"border-radius: 4px; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background-color: {theme['destructive']}; "
            f"color: white; border: 1px solid {theme['destructive']}; }}"
            f"QPushButton:disabled {{ background-color: {theme['surface']}; "
            f"color: {theme['text_dim']}; "
            f"border: 1px solid {theme['border']}; }}"
        )

    @staticmethod
    def get_toggle_button_style() -> str:
        """Returns QSS for persistent on/off toggle buttons (e.g. Snap, Legend).

        Uses a thick colored border when checked to signal persistent state,
        rather than a fill, which is reserved for active tool modes.

        Returns:
            str: QSS stylesheet string for toggle buttons.
        """
        theme = ThemeManager().get_theme()
        return (
            f"QPushButton {{ background-color: {theme['surface']}; "
            f"color: {theme['text_dim']}; border: 1px solid {theme['border']}; "
            f"border-radius: 4px; padding: 4px 8px; }}"
            f"QPushButton:hover {{ background-color: {theme['border']}; "
            f"color: {theme['text_main']}; }}"
            f"QPushButton:checked {{ background-color: {theme['surface']}; "
            f"color: {theme['text_main']}; "
            f"border: 2px solid {theme['accent_secondary']}; font-weight: bold; }}"
        )

    @staticmethod
    def get_ghost_destructive_button_style() -> str:
        """Returns QSS for a low-prominence destructive button.

        Transparent at rest with a red border/text; fills red on hover.
        Suitable for Delete buttons in compact panel headers.

        Returns:
            str: QSS stylesheet string for ghost destructive buttons.
        """
        theme = ThemeManager().get_theme()
        return (
            f"QPushButton {{ background-color: transparent; "
            f"color: {theme['destructive']}; "
            f"border: 1px solid {theme['destructive']}; "
            f"border-radius: 4px; padding: 4px 8px; }}"
            f"QPushButton:hover {{ background-color: {theme['destructive']}; "
            f"color: white; }}"
            f"QPushButton:disabled {{ color: {theme['text_dim']}; "
            f"border-color: {theme['border']}; }}"
        )

    @staticmethod
    def get_pill_painter_data(base_color: Optional[str] = None) -> dict:
        """
        Return RGB components and hex color for painting pill widgets.

        Parameters:
            base_color (Optional[str]): Optional hex color string in `#RRGGBB` form; when omitted the theme's `accent_secondary` color is used.

        Returns:
            dict: Mapping with keys:
                - "hex" (str): The hex color string used.
                - "r" (int): Red component (0-255).
                - "g" (int): Green component (0-255).
                - "b" (int): Blue component (0-255).
        """
        theme = ThemeManager().get_theme()
        hex_color = base_color or theme.get("accent_secondary", "#4A90D9")

        # Convert hex to rgba
        r, g, b = 74, 144, 217
        if hex_color.startswith("#") and len(hex_color) == 7:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)

        return {"hex": hex_color, "r": r, "g": g, "b": b}

    @staticmethod
    def get_pill_style(
        object_name: str,
        base_color: Optional[str] = None,
        has_delete: bool = False,
    ) -> str:
        """
        Generate themed QSS for a pill-style (rounded/oblong) widget.

        Parameters:
                object_name (str): The widget's objectName used as the selector.
                base_color (Optional[str]): Optional hex base color to derive pill RGB values; if omitted, theme accent_secondary is used.
                has_delete (bool): If True, include styling for an inline delete QToolButton inside the pill.

        Returns:
                str: QSS stylesheet string targeting the pill widget and optional delete button.
        """
        theme = ThemeManager().get_theme()
        data = StyleHelper.get_pill_painter_data(base_color)
        r, g, b = data["r"], data["g"], data["b"]

        # Main style is now transparent background to allow QPainter to draw the pill
        style = (
            f"#{object_name}, QFrame#{object_name} {{ "
            f"  background-color: transparent; "
            f"  border: none; "
            f"  margin: 2px; "
            f"}} "
            f"#{object_name} QLabel {{ "
            f"  color: {theme['text_main']}; "
            f"  border: none; background: transparent; "
            f"  font-size: 9pt; "
            f"  padding: 0 4px 0 8px; "
            f"}} "
        )

        if has_delete:
            style += (
                f"#{object_name} QToolButton {{ "
                f"  border: none; background: transparent; "
                f"  color: rgba({r}, {g}, {b}, 0.8); "
                f"  font-weight: bold; font-size: 10pt; "
                f"  padding: 0px 8px 0px 4px; "
                f"  margin: 0; "
                f"  border-radius: 10px; "
                f"}} "
                f"#{object_name} QToolButton:hover {{ "
                f"  color: {theme['error']}; "
                f"  background-color: rgba({r}, {g}, {b}, 0.2); "
                f"}} "
            )

        return style

    @staticmethod
    def get_icon_button_style() -> str:
        """
        QSS for square, icon-only buttons that reflect the current theme.

        Includes base, hover, and pressed states using theme surface, border, and app background colors.

        Returns:
            str: The QSS stylesheet string for icon buttons.
        """

        theme = ThemeManager().get_theme()
        return (
            f"QPushButton {{ background-color: {theme['surface']}; "
            f"border: 1px solid {theme['border']}; "
            f"border-radius: 4px; padding: 2px; }}"
            f"QPushButton:hover {{ background-color: {theme['border']}; }}"
            f"QPushButton:pressed {{ background-color: {theme['app_bg']}; }}"
        )

    @staticmethod
    def get_scroll_area_style() -> str:
        """Returns QSS for transparent scroll areas.

        Ensures scroll areas blend into the background.

        Returns:
            str: QSS stylesheet string.

        """
        return (
            "QScrollArea { background-color: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background-color: transparent; }"
        )

    @staticmethod
    def get_input_field_style() -> str:
        """Returns QSS for standard input fields.

        Provides consistent background, border, and rounded corners for inputs.

        Returns:
            str: QSS stylesheet string.

        """

        theme = ThemeManager().get_theme()
        return (
            f"background-color: {theme['surface']}; "
            f"color: {theme['text_main']}; "
            f"border: 1px solid {theme['border']}; "
            f"border-radius: 4px; padding: 1px;"
        )

    @staticmethod
    def get_transparent_input_style() -> str:
        """Returns QSS for transparent inner input widget.

        Used when the input is wrapped in a styled frame.
        """

        theme = ThemeManager().get_theme()
        return (
            f"background-color: transparent; color: {theme['text_main']}; border: none;"
        )

    @staticmethod
    def get_date_chip_style() -> str:
        """Returns QSS for the date chip frame (grouped year/month/day container).

        The chip frame provides a single unified border around the three date
        components, replacing their individual borders for a cleaner look.

        Returns:
            str: QSS stylesheet string for the date chip QFrame.

        """
        theme = ThemeManager().get_theme()
        return (
            f"QFrame#date_chip {{"
            f"background-color: {theme['surface']};"
            f"border: 1px solid {theme['border']};"
            f"border-radius: 4px;"
            f"}}"
        )

    @staticmethod
    def get_chip_spinbox_style() -> str:
        """Returns QSS for a spinbox inside a date chip (no outer border).

        Preserves the up/down arrow buttons while removing the outer border
        so the chip frame's border serves as the visual boundary.

        Returns:
            str: QSS stylesheet string for borderless spinboxes in chips.

        """
        from src.core.paths import get_resource_path

        theme = ThemeManager().get_theme()
        up_icon_path = get_resource_path(
            "default_assets/icons/ui_icons/arrow_up.svg"
        ).replace("\\", "/")
        down_icon_path = get_resource_path(
            "default_assets/icons/ui_icons/arrow_down.svg"
        ).replace("\\", "/")
        return (
            f"QSpinBox {{ background: transparent; border: none;"
            f" color: {theme['text_main']}; padding-right: 20px; }}"
            f"QSpinBox::up-button {{ subcontrol-origin: border;"
            f" subcontrol-position: top right; width: 16px; border: none;"
            f" background: transparent; margin-top: 1px; margin-right: 1px; }}"
            f"QSpinBox::down-button {{ subcontrol-origin: border;"
            f" subcontrol-position: bottom right; width: 16px; border: none;"
            f" background: transparent; margin-bottom: 1px; margin-right: 1px; }}"
            f"QSpinBox::up-button:hover, QSpinBox::down-button:hover {{"
            f" background: {theme['border']}; }}"
            f"QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{"
            f" background: {theme.get('primary', theme['border'])}; }}"
            f"QSpinBox::up-arrow {{ image: url('{up_icon_path}');"
            f" width: 10px; height: 10px; }}"
            f"QSpinBox::down-arrow {{ image: url('{down_icon_path}');"
            f" width: 10px; height: 10px; }}"
        )

    @staticmethod
    def get_chip_combo_style() -> str:
        """Returns QSS for a combobox inside a date chip (no outer border).

        Returns:
            str: QSS stylesheet string for borderless comboboxes in chips.

        """
        theme = ThemeManager().get_theme()
        return (
            f"QComboBox {{ background: transparent; border: none;"
            f" color: {theme['text_main']}; padding: 1px 4px; }}"
            f"QComboBox::drop-down {{ border: none; }}"
        )

    @staticmethod
    def get_temporal_card_style() -> str:
        """Returns QSS for the temporal range card container.

        The card visually groups start date, span, and end date into a
        cohesive section with a subtle border and rounded corners.

        Returns:
            str: QSS stylesheet string for the temporal range QFrame.

        """
        theme = ThemeManager().get_theme()
        return (
            f"QFrame#temporal_card {{"
            f"background-color: {theme['surface']};"
            f"border: 1px solid {theme['border']};"
            f"border-radius: 6px;"
            f"}}"
        )

    @staticmethod
    def get_temporal_separator_style() -> str:
        """Returns QSS for horizontal separator lines inside the temporal card.

        Returns:
            str: QSS stylesheet string for HLine QFrame separators.

        """
        theme = ThemeManager().get_theme()
        return f"color: {theme['border']};"

    @staticmethod
    def get_temporal_label_style() -> str:
        """Returns QSS for section labels inside the temporal range widget.

        Returns:
            str: QSS stylesheet string for Start/Span/End labels.

        """
        theme = ThemeManager().get_theme()
        return (
            f"color: {theme['text_dim']}; font-size: 11px;"
            f" font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;"
        )

    @staticmethod
    def get_temporal_lock_style(active: bool) -> str:
        """Returns QSS for the lock/anchor button in the temporal range widget.

        Args:
            active: True when end-date is locked (chain-break mode).

        Returns:
            str: QSS stylesheet string for the lock toggle button.

        """
        theme = ThemeManager().get_theme()
        if active:
            bg = theme.get("primary", "#4A90D9")
            border = bg
            hover = theme.get("accent_secondary", bg)
        else:
            bg = theme["surface"]
            border = theme["border"]
            hover = theme["border"]
        return (
            f"QPushButton {{ background-color: {bg}; border: 1px solid {border};"
            f" border-radius: 4px; padding: 2px; }}"
            f"QPushButton:hover {{ background-color: {hover}; }}"
        )

    @staticmethod
    def get_dialog_button_style(selected: bool) -> str:
        """Returns QSS for dialog day buttons.

        Used in calendar picker dialogs for day selection buttons.

        Args:
            selected: Whether this is the selected button style.

        Returns:
            str: QSS stylesheet string for dialog buttons.

        """

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
        """Returns base QSS for dialogs.

        Provides consistent dialog background and text colors.

        Returns:
            str: QSS stylesheet string for dialog base.

        """

        theme = ThemeManager().get_theme()
        return (
            f"QDialog {{ background-color: {theme['app_bg']}; "
            f"color: {theme['text_main']}; }}"
        )

    @staticmethod
    def get_scrollbar_style() -> str:
        """Returns QSS for custom scrollbars.

        Provides themed scrollbar styling matching the current theme.

        Returns:
            str: QSS stylesheet string for scrollbars.

        """

        theme = ThemeManager().get_theme()
        scrollbar_bg = theme.get("scrollbar_bg", "#2B2B2B")
        scrollbar_handle = theme.get("scrollbar_handle", "#555555")
        return (
            f"QScrollBar:vertical {{ "
            f"background-color: {scrollbar_bg}; "
            f"width: 10px; margin: 0px; }}"
            f"QScrollBar::handle:vertical {{ "
            f"background-color: {scrollbar_handle}; "
            f"min-height: 20px; border-radius: 5px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ "
            f"height: 0px; }}"
            f"QScrollBar:horizontal {{ "
            f"background-color: {scrollbar_bg}; "
            f"height: 10px; margin: 0px; }}"
            f"QScrollBar::handle:horizontal {{ "
            f"background-color: {scrollbar_handle}; "
            f"min-width: 20px; border-radius: 5px; }}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ "
            f"width: 0px; }}"
        )

    @staticmethod
    def get_tooltip_style() -> str:
        """Returns QSS for application wide tooltips.

        Provides consistent background, text, border, and padding using theme tokens.

        Returns:
            str: QSS stylesheet string for QToolTip.
        """
        theme = ThemeManager().get_theme()
        return (
            f"QToolTip {{ "
            f"background-color: {theme['surface']}; "
            f"color: {theme['text_main']}; "
            f"border: 1px solid {theme['border']}; "
            f"border-radius: 4px; "
            f"padding: 4px; }}"
        )

    @staticmethod
    def get_wiki_link_style(broken: bool = False) -> str:
        """Returns QSS for wiki links.

        Wiki links are styled differently based on whether they're broken
        (target doesn't exist) or valid.

        Args:
            broken: Whether this is a broken link style.

        Returns:
            str: QSS stylesheet string for wiki links.

        """

        theme = ThemeManager().get_theme()

        if broken:
            return f"color: {theme['error']}; text-decoration: underline dotted;"
        else:
            return f"color: {theme['accent_secondary']}; text-decoration: underline;"

    @staticmethod
    def get_timeline_header_style() -> str:
        """Returns QSS for timeline headers.

        Timeline headers use surface background with border.

        Returns:
            str: QSS stylesheet string for timeline headers.

        """

        theme = ThemeManager().get_theme()
        return (
            f"background-color: {theme['surface']}; "
            f"border-bottom: 1px solid {theme['border']}; "
            f"padding: 8px; font-weight: bold;"
        )

    @staticmethod
    def apply_standard_list_spacing(layout: QLayout) -> None:
        """Applies standard spacing for list layouts.

        Standard list spacing: 8px spacing, 16px margins (8-point grid).

        Args:
            layout: The QLayout to configure.

        """
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

    @staticmethod
    def apply_compact_spacing(layout: QLayout) -> None:
        """Applies compact spacing for dense layouts.

        Compact spacing: 4px spacing, 8px margins.

        Args:
            layout: The QLayout to configure.

        """
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)

    @staticmethod
    def apply_form_spacing(layout: QLayout) -> None:
        """Applies form spacing for form layouts.

        Form spacing: 8px spacing, 12px margins.

        Args:
            layout: The QLayout to configure.

        """
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

    @staticmethod
    def apply_no_margins(layout: QLayout) -> None:
        """
        Remove all margins from the given layout.

        Parameters:
            layout (QLayout): Layout to modify; margins will be set to 0 on all sides.
        """
        layout.setContentsMargins(0, 0, 0, 0)

    @staticmethod
    def get_checkbox_style() -> str:
        """
        QSS stylesheet for themed checkbox indicators and related view indicators.

        Returns:
            str: Stylesheet configuring checkbox, QListWidget/QListView/QTreeView indicators (size, border, radius, background), hover border color, checked state border and embedded check icon.
        """

        from src.core.paths import get_resource_path

        theme = ThemeManager().get_theme()

        # Use get_resource_path for robust absolute path resolution
        # (works in PyInstaller)
        # Ensure forward slashes and quoting to handle spaces/Windows issues
        check_icon_path = get_resource_path("default_assets/icons/ui_icons/check.svg")
        check_icon_path = check_icon_path.replace("\\", "/")
        icon_url = f"'{check_icon_path}'"

        return (
            f"QCheckBox {{ color: {theme['text_main']}; spacing: 8px; }}"
            f"QCheckBox::indicator, QListWidget::indicator, QListView::indicator, "
            f"QTreeView::indicator {{ "
            f"width: 16px; height: 16px; "
            f"border: 1px solid {theme['border']}; border-radius: 3px; "
            f"background-color: {theme['surface']}; }}"
            f"QCheckBox::indicator:unchecked:hover, "
            f"QListWidget::indicator:unchecked:hover, "
            f"QListView::indicator:unchecked:hover, "
            f"QTreeView::indicator:unchecked:hover {{ "
            f"border: 1px solid {theme['primary']}; }}"
            f"QCheckBox::indicator:checked, "
            f"QListWidget::indicator:checked, "
            f"QListView::indicator:checked, "
            f"QTreeView::indicator:checked {{ "
            f"border: 1px solid {theme['primary']}; "
            f"image: url({icon_url}); }}"
        )

    @staticmethod
    def get_list_widget_style() -> str:
        """Returns QSS for themed list widgets.

        Provides consistent background, text, border, and item hover colors.

        Returns:
            str: QSS stylesheet string for list widgets.
        """

        theme = ThemeManager().get_theme()
        primary = theme.get("primary", "#4A9EFF")

        # Create a semi-transparent version of the primary color for hover
        if len(primary) == 7 and primary.startswith("#"):
            r = int(primary[1:3], 16)
            g = int(primary[3:5], 16)
            b = int(primary[5:7], 16)
            hover_bg = f"rgba({r}, {g}, {b}, 0.1)"
        else:
            hover_bg = "rgba(74, 158, 255, 0.1)"

        return (
            f"QListWidget {{ "
            f"background-color: {theme['surface']}; "
            f"color: {theme['text_main']}; "
            f"border: 1px solid {theme['border']}; "
            f"border-radius: 4px; padding: 2px; }}"
            f"QListWidget::item {{ "
            f"padding: 4px; border-radius: 2px; }}"
            f"QListWidget::item:hover {{ "
            f"background-color: {hover_bg}; }}"
            f"QListWidget::item:selected {{ "
            f"background-color: {theme['border']}; "
            f"color: {theme['text_main']}; }}"
        )

    @staticmethod
    def get_tree_view_style() -> str:
        """Returns QSS for themed tree views (e.g. layer panel).

        Provides consistent background, text, selection, hover,
        branch indicators and scrollbar styling.

        Returns:
            str: QSS stylesheet string for QTreeView widgets.

        """

        theme = ThemeManager().get_theme()
        primary = theme.get("primary", "#4A9EFF")

        if len(primary) == 7 and primary.startswith("#"):
            r = int(primary[1:3], 16)
            g = int(primary[3:5], 16)
            b = int(primary[5:7], 16)
            hover_bg = f"rgba({r}, {g}, {b}, 0.1)"
        else:
            hover_bg = "rgba(74, 158, 255, 0.1)"

        return (
            f"QTreeView {{ "
            f"background-color: {theme['surface']}; "
            f"color: {theme['text_main']}; "
            f"border: 1px solid {theme['border']}; "
            f"border-radius: 4px; "
            f"outline: none; }}"
            f"QTreeView::item {{ "
            f"padding: 4px 2px; border-radius: 2px; }}"
            f"QTreeView::item:hover {{ "
            f"background-color: {hover_bg}; }}"
            f"QTreeView::item:selected {{ "
            f"background-color: {theme['border']}; "
            f"color: {theme['text_main']}; }}"
            f"QTreeView::branch:has-children:!has-siblings:closed,"
            f"QTreeView::branch:closed:has-children:has-siblings {{ "
            f"border-image: none; }}"
            f"QTreeView::branch:open:has-children:!has-siblings,"
            f"QTreeView::branch:open:has-children:has-siblings {{ "
            f"border-image: none; }}"
            + StyleHelper.get_scrollbar_style()
            + StyleHelper.get_checkbox_style()
        )

    @staticmethod
    def get_slider_style() -> str:
        """Returns QSS for themed sliders.

        Provides consistent groove, handle, and hover styling.

        Returns:
            str: QSS stylesheet string for QSlider widgets.

        """

        theme = ThemeManager().get_theme()
        return (
            f"QSlider::groove:horizontal {{ "
            f"border: 1px solid {theme['border']}; "
            f"height: 6px; "
            f"background: {theme['surface']}; "
            f"border-radius: 3px; }}"
            f"QSlider::handle:horizontal {{ "
            f"background: {theme['primary']}; "
            f"border: 1px solid {theme['primary']}; "
            f"width: 14px; margin: -5px 0; "
            f"border-radius: 7px; }}"
            f"QSlider::handle:horizontal:hover {{ "
            f"background: {theme['text_main']}; }}"
            f"QSlider::sub-page:horizontal {{ "
            f"background: {theme['primary']}; "
            f"border-radius: 3px; }}"
        )

    @staticmethod
    def get_panel_header_style() -> str:
        """Returns QSS for panel header labels (e.g. 'Layers' title).

        Returns:
            str: QSS stylesheet string for panel headers.

        """

        theme = ThemeManager().get_theme()
        return (
            f"color: {theme['text_main']}; font-weight: bold; font-size: 11pt; "
            f"padding: 2px 0px;"
        )

    @staticmethod
    def get_event_color() -> str:
        """Returns the theme-aware color for events.

        Returns:
            str: Hex color string.
        """

        theme = ThemeManager().get_theme()
        return theme.get("event_main", theme.get("primary", "#888888"))

    @staticmethod
    def get_entity_color() -> str:
        """Returns the theme-aware color for entities.

        Returns:
            str: Hex color string.
        """

        theme = ThemeManager().get_theme()
        return theme.get("entity_main", theme.get("accent_secondary", "#4A90D9"))

    @staticmethod
    def get_spinbox_style() -> str:
        """
        Generate QSS for themed QSpinBox widgets with custom up/down buttons.

        Prevents native arrows from being hidden when background or border styles are applied and uses bundled SVG arrow assets for the up/down controls.

        Returns:
            str: QSS stylesheet string for QSpinBox widgets.
        """
        from src.core.paths import get_resource_path

        theme = ThemeManager().get_theme()
        base_style = StyleHelper.get_input_field_style()

        # Get raw file paths and convert to forward slashes for CSS
        up_icon_path = get_resource_path(
            "default_assets/icons/ui_icons/arrow_up.svg"
        ).replace("\\", "/")
        down_icon_path = get_resource_path(
            "default_assets/icons/ui_icons/arrow_down.svg"
        ).replace("\\", "/")

        return (
            f"QSpinBox {{ {base_style} padding-right: 20px; }}"
            f"QSpinBox::up-button {{ "
            f"subcontrol-origin: border; subcontrol-position: top right; "
            f"width: 16px; border: none; "
            f"background-color: transparent; "
            f"margin-top: 1px; margin-right: 1px; }}"
            f"QSpinBox::down-button {{ "
            f"subcontrol-origin: border; subcontrol-position: bottom right; "
            f"width: 16px; border: none; "
            f"background-color: transparent; "
            f"margin-bottom: 1px; margin-right: 1px; }}"
            f"QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ "
            f"background-color: {theme['border']}; }}"
            f"QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{ "
            f"background-color: {theme['primary']}; }}"
            f"QSpinBox::up-arrow {{ "
            f"image: url('{up_icon_path}'); width: 10px; height: 10px; }}"
            f"QSpinBox::down-arrow {{ "
            f"image: url('{down_icon_path}'); width: 10px; height: 10px; }}"
        )

    @staticmethod
    def get_shortcut_key_style() -> str:
        """
        QSS for keyboard shortcut key widgets styled as monospace, bold tokens with padding and rounded borders.

        Returns:
            str: Stylesheet string using the theme's surface, text_main, and border colors.
        """

        theme = ThemeManager().get_theme()
        return (
            f"background-color: {theme['surface']}; color: {theme['text_main']}; "
            f"border: 1px solid {theme['border']}; border-radius: 4px; "
            f"padding: 4px; font-weight: bold;"
            f"font-family: monospace; font-weight: bold;"
        )

    @staticmethod
    def get_content_header_style() -> str:
        """Returns QSS for content headers (About dialog etc.).

        Returns:
            str: QSS stylesheet string.
        """

        theme = ThemeManager().get_theme()
        return (
            f"color: {theme['primary']}; "
            f"font-size: {theme.get('font_size_h1', '14pt')}; "
            f"font-weight: bold; margin-bottom: 8px;"
        )

    @staticmethod
    def get_timeline_display_css() -> str:
        """Returns CSS for TimelineDisplayWidget HTML content.

        Provides theme-aware styling for the timeline event display,
        including borders, colors, and separators.

        Returns:
            str: CSS stylesheet string for HTML content.
        """

        theme = ThemeManager().get_theme()
        return f"""
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }}
            .timeline-entry {{
                padding: 8px 10px;
                margin: 6px 2px;
                border-radius: 3px;
                border: 1px solid {theme["border"]};
            }}
            .timeline-entry.active {{
                border-color: {theme["primary"]};
                border-width: 2px;
            }}
            .timeline-entry.future {{
                opacity: 0.5;
                border-color: {theme["border"]};
            }}
            .event-header {{ margin-bottom: 4px; }}
            .event-date {{
                color: {theme["text_dim"]};
                font-size: 11px;
                font-weight: 500;
            }}
            .event-name {{
                color: {theme["text_main"]};
                font-weight: 600;
                font-size: 13px;
            }}
            .event-type {{
                color: {theme["text_dim"]};
                font-size: 10px;
                font-style: italic;
            }}
            .payload-list {{
                margin: 4px 0 0 16px;
                padding: 0;
            }}
            .payload-item {{
                color: {theme["text_dim"]};
                font-size: 11px;
                line-height: 1.4;
            }}
            .payload-key {{ color: {theme["accent_secondary"]}; }}
            .payload-value {{ color: {theme["primary"]}; }}
            .now-separator {{
                display: flex;
                align-items: center;
                margin: 12px 0;
                color: {theme["primary"]};
                font-size: 10px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .now-separator::before,
            .now-separator::after {{
                content: '';
                flex: 1;
                height: 1px;
                background: linear-gradient(
                    to right, transparent, {theme["primary"]}, transparent
                );
            }}
            .now-separator span {{
                padding: 0 10px;
            }}
            .now-line {{
                display: flex;
                align-items: center;
                margin: 12px 0;
                color: {theme["accent_secondary"]};
                font-size: 10px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .now-line::before,
            .now-line::after {{
                content: '';
                flex: 1;
                height: 2px;
                background: {theme["accent_secondary"]};
            }}
            .now-line span {{
                padding: 0 10px;
            }}
        """

    @staticmethod
    def get_drag_overlay_style() -> str:
        """Returns QSS for drag-and-drop overlay hints.

        Provides a consistent blue dashed overlay with semi-transparent background.

        Returns:
            str: QSS stylesheet string for drag overlays.
        """
        return """
            QLabel {
                background-color: rgba(51, 153, 255, 0.15);
                border: 2px dashed #3399FF;
                border-radius: 6px;
                color: #3399FF;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
            }
        """

    @staticmethod
    def get_overlay_banner_style() -> str:
        """Returns QSS for the semi-transparent overlay banner on the map view.

        Returns:
            str: QSS stylesheet string for overlay banners.
        """
        theme = ThemeManager().get_theme()
        bg = theme.get("surface_alt", "rgba(0, 0, 0, 180)")
        return (
            "QLabel {"
            f"  background-color: {bg};"
            "  color: white;"
            "  padding: 12px;"
            "  border-bottom-left-radius: 8px;"
            "  border-bottom-right-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "}"
        )

    @staticmethod
    def get_legend_overlay_style() -> str:
        """Returns QSS for the floating raster legend overlay.

        Returns:
            str: QSS stylesheet string for legend overlays.
        """
        theme = ThemeManager().get_theme()
        bg = theme.get("surface_alt", "#2A2A2A")
        border = theme.get("border", "#444444")
        return (
            "QWidget {"
            f"  background-color: {bg};"
            f"  border: 1px solid {border};"
            "  border-radius: 6px;"
            "}"
        )

    @staticmethod
    def get_probe_popup_style() -> str:
        """Returns QSS for the raster probe popup overlay label.

        Returns:
            str: QSS stylesheet string for the probe popup.
        """
        theme = ThemeManager().get_theme()
        bg = theme.get("surface_alt", "#2A2A2A")
        text = theme.get("text_main", "#E8E8E8")
        border = theme.get("border", "#444444")
        return (
            "QLabel#RasterProbePopup {"
            f"  background-color: {bg};"
            f"  color: {text};"
            f"  border: 1px solid {border};"
            "  border-radius: 6px;"
            "  padding: 6px 10px;"
            "  font-size: 12px;"
            "}"
        )

    @staticmethod
    def get_mode_indicator_style(bg_color: str) -> str:
        """Returns QSS for the toolbar mode-indicator label.

        Args:
            bg_color: Background hex colour for the current mode.

        Returns:
            str: QSS stylesheet string for mode indicator labels.
        """
        return (
            "QLabel {"
            f"  background: {bg_color};"
            "  color: white;"
            "  padding: 5px 12px;"
            "  border-radius: 4px;"
            "  font-weight: bold;"
            "  font-size: 11px;"
            "}"
        )

    @staticmethod
    def get_mode_pill_style(bg_color: str, active: bool = False) -> str:
        """Returns QSS for the toolbar mode indicator as a clickable pill button.

        In normal (inactive) mode the pill is a low-weight outlined badge.
        In active modes it fills with the mode color and becomes a prominent
        clickable target that the user can press to exit the mode.

        Args:
            bg_color: Hex color for the current mode.
            active: True when a special mode (clock/draft/drawing/vertex) is active.

        Returns:
            str: QSS stylesheet string for the mode pill button.
        """
        if active:
            return (
                f"QPushButton {{ background-color: {bg_color}; color: white; "
                f"border: none; border-radius: 10px; padding: 4px 12px; "
                f"font-weight: bold; font-size: 11px; }}"
                f"QPushButton:hover {{ border: 2px solid white; }}"
            )
        return (
            f"QPushButton {{ background-color: transparent; color: {bg_color}; "
            f"border: 1px solid {bg_color}; border-radius: 10px; "
            f"padding: 4px 10px; font-size: 11px; }}"
        )

    @staticmethod
    def get_toolbar_spacing_style() -> str:
        """Returns QSS for map toolbar spacing.

        Returns:
            str: QSS stylesheet string for toolbar spacing.
        """
        return "QToolBar { spacing: 4px; padding: 4px; }"

    @staticmethod
    def get_raster_mode_badge_style(bg_color: str) -> str:
        """Returns QSS for the raster mode badge label.

        Args:
            bg_color: Background hex colour for the badge.

        Returns:
            str: QSS stylesheet string for raster mode badges.
        """
        return (
            "QLabel#RasterModeBadge {"
            f"  background-color: {bg_color};"
            "  color: #FFFFFF;"
            "  border-radius: 4px;"
            "  padding: 2px 8px;"
            "  font-size: 8pt;"
            "  font-weight: bold;"
            "}"
        )

    @staticmethod
    def get_section_separator_style() -> Tuple[str, str]:
        """Returns QSS for the section separator label and line.

        Returns:
            A ``(label_style, line_style)`` tuple where *label_style* is
            the QSS for the section heading text and *line_style* is the
            QSS for the horizontal rule.
        """
        theme = ThemeManager().get_theme()
        dim_color = theme.get("text_dim", "#888888")
        border_color = theme.get("border", "#333344")
        label_style = (
            f"color: {dim_color}; font-size: 8pt; font-weight: bold;"
        )
        line_style = (
            f"color: {border_color}; background: {border_color};"
        )
        return label_style, line_style

    @staticmethod
    def get_dim_text_color() -> str:
        """Returns the theme-aware dim text colour hex string.

        Returns:
            str: Hex colour suitable for subdued/secondary text.
        """
        theme = ThemeManager().get_theme()
        return theme.get("text_dim", "#888888")
