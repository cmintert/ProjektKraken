"""Progress Dialog Module.

Provides a simple, reusable progress dialog for long-running operations.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QProgressDialog, QWidget


class ProgressDialog(QProgressDialog):
    """Reusable progress dialog for long-running operations.

    Displays an indeterminate progress bar by default, suitable for operations
    where progress cannot be measured (like imports/exports).

    Features:
    - Modal by default (blocks interaction with parent)
    - Cannot be cancelled by default (for data integrity)
    - Auto-shows after construction
    - Clean, consistent styling
    """

    def __init__(
        self,
        label_text: str,
        parent: Optional[QWidget] = None,
        cancelable: bool = False,
        title: str = "Please Wait",
    ) -> None:
        """Initialize the progress dialog.

        Args:
            label_text: Text to display above the progress bar.
            parent: Parent widget (for proper modal behavior).
            cancelable: If True, shows a cancel button. Default False.
            title: Window title. Default "Please Wait".
        """
        # Create indeterminate progress (0, 0 range)
        cancel_text = "Cancel" if cancelable else ""
        super().__init__(label_text, cancel_text, 0, 0, parent)

        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumDuration(0)  # Show immediately
        self.setAutoReset(False)
        self.setAutoClose(False)

        # Style for consistency
        self.setMinimumWidth(400)

    def update_text(self, text: str) -> None:
        """Update the label text during operation.

        Args:
            text: New text to display.
        """
        self.setLabelText(text)

    def finish(self) -> None:
        """Close the dialog when operation completes."""
        self.close()
