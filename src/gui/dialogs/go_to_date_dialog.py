"""Calendar-aware exact-date navigation for the timeline playhead."""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from src.core.calendar import CalendarConverter
from src.core.date_parser import DateParser
from src.core.temporal_expression import TemporalPrecision, TemporalQualifier
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.compact_date_widget import CompactDateWidget


class GoToDateDialog(QDialog):
    """Collect one complete calendar date without creating temporal evidence."""

    def __init__(
        self,
        converter: CalendarConverter,
        playhead_time: float,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the dialog at the current playhead date."""
        super().__init__(parent)
        self.setWindowTitle("Go to date")
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self._converter = converter
        self._parser = DateParser(converter._config)
        self.target_time: float | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enter an exact date in the active calendar."))
        self.date_input = CompactDateWidget(self, text_first=True)
        self.date_input.set_calendar_converter(converter)
        self.date_input.set_value(playhead_time)
        # Qualification and occurrence limits are authoring tools, not navigation.
        self.date_input.date_fields_button.hide()
        self.date_input.btn_time_toggle.setMaximumWidth(120)
        layout.addWidget(self.date_input)

        self.feedback = QLabel(self)
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        """Accept only a real, fully specified instant on this calendar."""
        try:
            expression = self._parser.parse_expression(
                self.date_input.txt_date.text().strip()
            )
            if (
                expression.year is None
                or expression.month is None
                or expression.day is None
                or expression.precision
                not in {
                    TemporalPrecision.DAY,
                    TemporalPrecision.HOUR,
                    TemporalPrecision.MINUTE,
                }
                or expression.qualifier != TemporalQualifier.ASSERTED
                or expression.explicit_outer_start is not None
                or expression.explicit_outer_end is not None
            ):
                raise ValueError("Enter a complete, exact day with optional time.")
            self.target_time = self._converter.resolve_precision_bounds(expression)[0]
        except (ValueError, TypeError, IndexError, OverflowError):
            self.feedback.setText(
                "Enter a valid, complete date in this calendar. "
                "Ranges and uncertain dates cannot position the playhead."
            )
            return
        super().accept()
