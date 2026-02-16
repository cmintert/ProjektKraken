"""Standard Buttons Module.

Provides lightweight button wrappers with standardized properties. Visual styling is
handled via StyleHelper QSS or global QSS.
"""

from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QCheckBox, QPushButton, QWidget


class StandardButton(QPushButton):
    """A standard button with consistent sizing.

    Actual visual styling is applied via StyleHelper or global QSS.
    """

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        """Initializes a standard button.

        Args:
            text: The button text.
            parent: The parent widget, if any.

        """
        super().__init__(text, parent)
        self.setMinimumHeight(32)  # 8-point grid: 4 units


class IconButton(QPushButton):
    """A fixed-size button optimized for icons.

    Useful for toolbar buttons with icons only.
    """

    def __init__(
        self, text: str = "", parent: Optional[QWidget] = None, size: int = 32
    ) -> None:
        """Initializes an icon button.

        Args:
            text: The button text or icon character.
            parent: The parent widget, if any.
            size: The fixed size in pixels (default 32, 8-point grid: 4 units).

        """
        super().__init__(text, parent)
        self.setFixedSize(QSize(size, size))


class PrimaryButton(StandardButton):
    """A primary action button.

    Applies StyleHelper primary button styling.
    """

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        """Initializes a primary button.

        Args:
            text: The button text.
            parent: The parent widget, if any.

        """
        super().__init__(text, parent)
        self._apply_style()

        from src.core.theme_manager import ThemeManager

        ThemeManager().theme_changed.connect(self._on_theme_changed)

    def _apply_style(self) -> None:
        """Applies the current theme style."""
        from src.gui.utils.style_helper import StyleHelper

        self.setStyleSheet(StyleHelper.get_primary_button_style())

    def _on_theme_changed(self) -> None:
        """Handles theme change events."""
        self._apply_style()


class DestructiveButton(StandardButton):
    """A destructive action button.

    Applies StyleHelper destructive button styling (e.g. for Delete/Remove).
    """

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        """Initializes a destructive button.

        Args:
            text: The button text.
            parent: The parent widget, if any.

        """
        super().__init__(text, parent)
        self._apply_style()

        from src.core.theme_manager import ThemeManager

        ThemeManager().theme_changed.connect(self._on_theme_changed)

    def _apply_style(self) -> None:
        """Applies the current theme style."""
        from src.gui.utils.style_helper import StyleHelper

        self.setStyleSheet(StyleHelper.get_destructive_button_style())

    def _on_theme_changed(self) -> None:
        """Handles theme change events."""
        self._apply_style()


class StandardCheckbox(QCheckBox):
    """A standard checkbox with consistent styling.

    Applies StyleHelper checkbox styling and updates on theme changes.
    """

    def __init__(self, text: str = "", parent: Optional[QWidget] = None) -> None:
        """Initializes a standard checkbox.

        Args:
            text: The checkbox text.
            parent: The parent widget, if any.
        """
        super().__init__(text, parent)
        self._apply_style()

        from src.core.theme_manager import ThemeManager

        ThemeManager().theme_changed.connect(self._on_theme_changed)

    def _apply_style(self) -> None:
        """Applies the current theme style."""
        from src.gui.utils.style_helper import StyleHelper

        self.setStyleSheet(StyleHelper.get_checkbox_style())

    def _on_theme_changed(self) -> None:
        """Handles theme change events."""
        self._apply_style()
