from dataclasses import dataclass
from PySide6.QtGui import QKeySequence


@dataclass
class KeyboardShortcut:
    """Represents a keyboard shortcut with metadata."""

    name: str
    sequence: str
    description: str

    @property
    def key_sequence(self) -> QKeySequence:
        """Returns the QKeySequence object."""
        return QKeySequence(self.sequence)

    @property
    def tooltip(self) -> str:
        """Returns a standardized tooltip string."""
        return f"{self.description} ({self.sequence})"


class ShortcutManager:
    """Centralized manager for application keyboard shortcuts."""

    CREATE_EVENT = KeyboardShortcut("Create Event", "Ctrl+E", "Create a new event")

    CREATE_ENTITY = KeyboardShortcut("Create Entity", "Ctrl+I", "Create a new entity")

    CREATE_MAP = KeyboardShortcut("Create Map", "Ctrl+M", "Create a new map")

    # Formatting Shortcuts (WikiTextEdit)
    FORMAT_BOLD = KeyboardShortcut("Bold", "Ctrl+B", "Toggle bold")
    FORMAT_ITALIC = KeyboardShortcut("Italic", "Ctrl+I", "Toggle italic")
    FORMAT_H1 = KeyboardShortcut("Heading 1", "Ctrl+1", "Set text to Heading 1")
    FORMAT_H2 = KeyboardShortcut("Heading 2", "Ctrl+2", "Set text to Heading 2")
    FORMAT_H3 = KeyboardShortcut("Heading 3", "Ctrl+3", "Set text to Heading 3")
    FORMAT_BODY = KeyboardShortcut("Body Text", "Ctrl+0", "Reset to body text")

    # Outline Shortcuts (Longform)
    OUTLINE_PROMOTE = KeyboardShortcut(
        "Promote Item", "Ctrl+[", "Promote item in outline"
    )
    OUTLINE_DEMOTE = KeyboardShortcut("Demote Item", "Ctrl+]", "Demote item in outline")

    @classmethod
    def get_tooltip(cls, shortcut: KeyboardShortcut) -> str:
        """Helper to get tooltip for a shortcut."""
        return shortcut.tooltip

    @staticmethod
    def check_event(event, shortcut: KeyboardShortcut) -> bool:
        """Checks if a QKeyEvent matches a shortcut.

        Args:
            event: The QKeyEvent to check.
            shortcut: The KeyboardShortcut to match against.

        Returns:
            bool: True if it matches.
        """
        if hasattr(event, "keyCombination"):
            # Qt 6.0+
            event_seq = QKeySequence(event.keyCombination())
        else:
            # Fallback for older versions or if keyCombination is missing
            # Combine modifiers and key to an integer
            try:
                # Try to get integer value if it's an enum
                mod_val = event.modifiers().value
            except AttributeError:
                mod_val = int(event.modifiers())

            event_seq = QKeySequence(mod_val | event.key())

        return (
            event_seq.matches(shortcut.key_sequence)
            == QKeySequence.SequenceMatch.ExactMatch
        )
