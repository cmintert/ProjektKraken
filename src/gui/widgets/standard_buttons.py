"""Standard Buttons Module.

Provides lightweight button wrappers with standardized properties. Visual styling is
handled via StyleHelper QSS or global QSS.
"""

from typing import Optional

from PySide6.QtCore import QEvent, QSize
from PySide6.QtWidgets import QCheckBox, QPushButton, QToolButton, QWidget


class StandardButton(QPushButton):
    """A standard button with consistent sizing.

    Actual visual styling is applied via StyleHelper or global QSS.
    """

    def __init__(
        self, text: str | QWidget = "", parent: Optional[QWidget] = None
    ) -> None:
        """Initializes a standard button.

        Args:
            text: The button text.
            parent: The parent widget, if any.

        """
        if isinstance(text, QWidget):
            parent, text = text, ""
        super().__init__(text, parent)
        self._label_sizing_ready = True
        self.setMinimumHeight(32)  # 8-point grid: 4 units

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Refresh intrinsic height after style/font changes invalidate Qt hints."""
        super().changeEvent(event)
        if getattr(self, "_label_sizing_ready", False) and event.type() in (
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
        ):
            if not callable(getattr(self, "label_geometry", None)):
                self.setMinimumHeight(max(32, self.sizeHint().height()))
            self.updateGeometry()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Prevent parent layouts from shrinking the styled action label."""
        return self.sizeHint()

    def sizeHint(self) -> QSize:  # noqa: N802
        """Reserve the complete styled wording when the font changes."""
        from src.gui.utils.action_label_metrics import action_label_geometry

        hint = super().sizeHint()
        geometry = action_label_geometry(self, hint)
        return hint + QSize(
            max(0, geometry.required.width() - geometry.available.width()),
            max(0, geometry.required.height() - geometry.available.height()),
        )


class LabelSizedToolButton(QToolButton):
    """A labeled tool whose style hint reserves complete text and decoration."""

    def sizeHint(self) -> QSize:  # noqa: N802
        """Include styled text, icons and menu decoration in both dimensions."""
        from src.gui.utils.action_label_metrics import action_label_geometry

        hint = super().sizeHint()
        geometry = action_label_geometry(self, hint)
        return hint.expandedTo(geometry.required)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Prevent shrinking a labeled tool below its complete wording."""
        return self.sizeHint()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Invalidate containing layouts when style/font content changes."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            if not callable(getattr(self, "label_geometry", None)):
                self.setMinimumHeight(self.sizeHint().height())
            self.updateGeometry()


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
