"""Regression tests for shared Analysis Suite table presentation."""

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QAbstractItemView, QTableWidgetItem

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.analysis._analysis_utils import (
    get_analysis_table_style,
    make_analysis_table,
    make_text_cell,
)


@pytest.mark.unit
def test_analysis_table_uses_full_row_primary_selection(qapp):
    """Analysis rows use the same strong primary selection as navigation."""
    table = make_analysis_table(["Name", "Message"])
    theme = ThemeManager().get_theme()
    contrast = StyleHelper.get_contrasting_text_color(theme["primary"])

    assert table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows
    assert table.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection
    assert theme["primary"] in get_analysis_table_style()
    assert contrast in get_analysis_table_style()


@pytest.mark.unit
def test_embedded_message_cell_tracks_row_selection(qapp):
    """A message widget must not leave a hole in the selected-row highlight."""
    table = make_analysis_table(["Name", "Message"])
    table.setRowCount(1)
    table.setItem(0, 0, QTableWidgetItem("Selected finding"))
    message = make_text_cell("A message that remains readable when selected.")
    table.setCellWidget(0, 1, message)

    table.selectRow(0)
    qapp.processEvents()

    theme = ThemeManager().get_theme()
    assert theme["primary"] in message.styleSheet()
    assert StyleHelper.get_contrasting_text_color(theme["primary"]) in (
        message.styleSheet()
    )

    table.clearSelection()
    qapp.processEvents()
    assert "background-color: transparent" in message.styleSheet()


@pytest.mark.unit
def test_clicking_embedded_message_selects_its_row(qapp, qtbot):
    """Clicking selectable message text still activates the complete row."""
    table = make_analysis_table(["Name", "Message"])
    qtbot.addWidget(table)
    table.setRowCount(1)
    table.setItem(0, 0, QTableWidgetItem("Finding"))
    message = make_text_cell("Click this message")
    table.setCellWidget(0, 1, message)
    table.show()
    qapp.processEvents()

    qtbot.mouseClick(
        message.viewport(),
        Qt.MouseButton.LeftButton,
        pos=QPoint(4, 4),
    )

    assert [index.row() for index in table.selectionModel().selectedRows()] == [0]


@pytest.mark.unit
def test_long_message_expands_row_to_wrapped_content(qapp, qtbot):
    """Long analysis text grows vertically instead of being clipped."""
    table = make_analysis_table(["Message"])
    qtbot.addWidget(table)
    table.resize(360, 180)
    table.setRowCount(1)
    message = make_text_cell(
        "This intentionally long validation message must wrap across several "
        "lines so every word remains visible within the analysis result row. "
        "The row height should follow the reflowed document content."
    )
    table.setCellWidget(0, 0, message)
    table.show()
    qapp.processEvents()
    table.resizeRowsToContents()
    qapp.processEvents()

    assert message.sizeHint().height() > 32
    assert table.rowHeight(0) >= message.sizeHint().height()
