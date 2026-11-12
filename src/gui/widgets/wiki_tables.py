"""Visual GFM table editing and serialization for description documents."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPointF, Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QFontDatabase,
    QKeyEvent,
    QPainter,
    QPen,
    QTextBlock,
    QTextCharFormat,
    QTextCursor,
    QTextLength,
    QTextTable,
)
from PySide6.QtWidgets import QMenu

from src.core.markdown_content import parse_content
from src.core.theme_manager import ThemeManager
from src.core.wiki_markdown_grammar import requires_source_mode
from src.gui.utils.help_context import declare_inspection

if TYPE_CHECKING:
    from src.gui.widgets.wiki_text_edit import WikiTextEditView

_BOLD_WEIGHT_THRESHOLD = 600


def tables(view: WikiTextEditView) -> list[QTextTable]:
    """Return top-level GFM tables in document order."""
    return [
        frame
        for frame in view.document().rootFrame().childFrames()
        if isinstance(frame, QTextTable)
    ]


def has_table(source: str) -> bool:
    """Identify actual parsed tables rather than pipe-like prose."""
    return any(token.type == "table_open" for token in parse_content(source).tokens)


def _cell_inline(block: QTextBlock) -> str:
    output = []
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        iterator += 1
        if not fragment.isValid():
            continue
        fmt = fragment.charFormat()
        text = fragment.text().replace("\u2028", " ")
        # Escape authored punctuation before applying semantic delimiters.
        text = re.sub(r"([\\`*_\[\]<>~|])", r"\\\1", text)
        if fmt.isAnchor():
            target = fmt.anchorHref().replace("|", "\\|")
            if target.startswith("id:") or not re.match(r"[\w+.-]+:|[/#]", target):
                text = f"[[{target}\\|{text}]]"
            else:
                target = target.replace("(", "%28").replace(")", "%29")
                text = f"[{text}](<{target}>)"
        if fmt.fontFixedPitch():
            literal = fragment.text().replace("|", "\\|")
            runs = [len(run) for run in re.findall(r"`+", literal)]
            fence = "`" * (max(runs, default=0) + 1)
            text = f"{fence} {literal} {fence}"
        if fmt.fontWeight() > _BOLD_WEIGHT_THRESHOLD:
            text = _mark(text, "**")
        if fmt.fontItalic():
            text = _mark(text, "*")
        if fmt.fontStrikeOut():
            text = _mark(text, "~~")
        output.append(text)
    return "".join(output)


def _mark(text: str, marker: str) -> str:
    """Keep whitespace outside emphasis delimiters so GFM recognizes them."""
    content = text.strip()
    if not content:
        return text
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    return f"{leading}{marker}{content}{marker}{trailing}"


def serialize_table(table: QTextTable) -> str:
    """Write a rectangular table with one header row as portable GFM."""
    rows = []
    for row in range(table.rows()):
        cells = []
        for column in range(table.columns()):
            cell = table.cellAt(row, column)
            block = cell.firstCursorPosition().block()
            parts = []
            while block.isValid() and block.position() <= cell.lastPosition():
                parts.append(_cell_inline(block))
                block = block.next()
            cells.append(" ".join(parts).strip())
        rows.append("| " + " | ".join(cells) + " |")
    alignment = []
    for column in range(table.columns()):
        value = table.cellAt(0, column).firstCursorPosition().blockFormat().alignment()
        alignment.append(
            ":---:"
            if value & Qt.AlignmentFlag.AlignHCenter
            else "---:"
            if value & Qt.AlignmentFlag.AlignRight
            else ":---"
        )
    rows.insert(1, "| " + " | ".join(alignment) + " |")
    return "\n".join(rows)


def document_blocks(view: WikiTextEditView) -> list[str]:
    """Serialize each root block/frame once, retaining surrounding prose."""
    result = []
    iterator = view.document().rootFrame().begin()
    while not iterator.atEnd():
        frame, block = iterator.currentFrame(), iterator.currentBlock()
        if isinstance(frame, QTextTable):
            result.append(serialize_table(frame))
        elif block.isValid():
            # Qt requires empty sentinel blocks immediately around tables.
            if block.text() or block.blockFormat().headingLevel():
                result.append(view._process_block(block))
        iterator += 1
    return result


class WikiTableController(QObject):
    """Keep table operations local, reversible and reachable through Insert."""

    def __init__(self, view: WikiTextEditView) -> None:
        """Bind the feature to a narrow description editing surface."""
        super().__init__(view)
        self.view = view
        self.actions: dict[str, QAction] = {}
        self._code_ranges: list[tuple[int, int]] = []
        commands = {
            "Insert table": self.insert,
            "Insert row above": lambda: self.row(False),
            "Insert row below": lambda: self.row(True),
            "Delete row": self.delete_row,
            "Insert column left": lambda: self.column(False),
            "Insert column right": lambda: self.column(True),
            "Delete column": self.delete_column,
            "Delete table": self.delete,
            "Align column left": lambda: self.align(Qt.AlignmentFlag.AlignLeft),
            "Align column center": lambda: self.align(Qt.AlignmentFlag.AlignHCenter),
            "Align column right": lambda: self.align(Qt.AlignmentFlag.AlignRight),
        }
        for title, callback in commands.items():
            action = declare_inspection(
                QAction(title, self),
                "writing.tables|writing.edit|help-inspect-writing-tables",
            )
            action.triggered.connect(callback)
            self.actions[title] = action
        self.strike = declare_inspection(
            QAction("Strikethrough", self),
            "writing.tables|writing.edit|help-inspect-writing-tables",
        )
        self.strike.triggered.connect(self.toggle_strike)
        view.cursorPositionChanged.connect(self.refresh)
        view.view_mode_changed.connect(self.refresh)

    def install_menu(self, insert_menu: QMenu) -> None:
        """Use the existing visible Insert menu rather than more toolbar chrome."""
        self.menu = QMenu("Table", insert_menu)
        insert_menu.addMenu(self.menu)
        menu = self.menu
        for action in self.actions.values():
            menu.addAction(action)
        menu.aboutToShow.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args: object) -> None:
        """Explain permissions and table-context prerequisites in disabled actions."""
        editable = not self.view.isReadOnly() and self.view._view_mode == "rich"
        current = self.view.textCursor().currentTable()
        self.strike.setEnabled(editable and current is not None)
        self.strike.setToolTip("Toggle strikethrough in an editable table cell")
        self.view.setProperty(
            "descriptionTableNavigation",
            current is not None and self.view._view_mode == "rich",
        )
        for action in (self.view.action_h1, self.view.action_h2, self.view.action_h3):
            action.setEnabled(not self.view.isReadOnly() and current is None)
        for title, action in self.actions.items():
            enabled = editable and (
                current is None if title == "Insert table" else current is not None
            )
            action.setEnabled(enabled)
            action.setToolTip(
                title
                if enabled
                else "Use editable Rich view; place the cursor outside a table to insert, or inside one to change it."
            )

    def _edit(self, operation: Callable[[QTextTable, QTextCursor], None]) -> None:
        if self.view.isReadOnly() or self.view._view_mode != "rich":
            return
        cursor = self.view.textCursor()
        table = cursor.currentTable()
        if table is None:
            return
        cursor.beginEditBlock()
        operation(table, cursor)
        if any(item is table for item in tables(self.view)):
            self._column_alignment(table)
        cursor.endEditBlock()
        self.view.setTextCursor(cursor)
        self.view.setFocus(Qt.FocusReason.OtherFocusReason)
        self.refresh()

    @staticmethod
    def _column_alignment(table: QTextTable) -> None:
        for column in range(table.columns()):
            alignment = (
                table.cellAt(0, column).firstCursorPosition().blockFormat().alignment()
            )
            for row in range(1, table.rows()):
                target = table.cellAt(row, column).firstCursorPosition()
                fmt = target.blockFormat()
                fmt.setAlignment(alignment)
                target.setBlockFormat(fmt)

    def prepare(self) -> None:
        """Set GFM table layout only while loading a fresh projection."""
        for table in tables(self.view):
            self._layout(table)
        for start, length in self._code_ranges:
            cursor = QTextCursor(self.view.document())
            cursor.setPosition(start)
            cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setFontFixedPitch(True)
            fmt.setFontFamilies(
                QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).families()
            )
            cursor.mergeCharFormat(fmt)
        self._code_ranges.clear()

    def remember_code(self) -> None:
        """Retain semantic code spans before ordinary typography normalizes fonts."""
        self._code_ranges.clear()
        block = self.view.document().begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                iterator += 1
                if fragment.isValid() and "monospace" in (
                    fragment.charFormat().fontFamilies() or []
                ):
                    self._code_ranges.append((fragment.position(), fragment.length()))
            block = block.next()

    @staticmethod
    def _layout(table: QTextTable) -> None:
        fmt = table.format()
        fmt.setBorder(0)
        fmt.setCellPadding(6)
        fmt.setCellSpacing(0)
        fmt.setHeaderRowCount(1)
        fmt.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        table.setFormat(fmt)

    def insert(self) -> None:
        """Insert a small table immediately; grow it through the same menu."""
        if (
            self.view.isReadOnly()
            or self.view._view_mode != "rich"
            or self.view.textCursor().currentTable()
        ):
            return
        cursor = self.view.textCursor()
        cursor.beginEditBlock()
        table = cursor.insertTable(3, 2)
        self._layout(table)
        cursor.endEditBlock()
        self.view.setTextCursor(table.cellAt(0, 0).firstCursorPosition())
        self.view.setFocus(Qt.FocusReason.OtherFocusReason)

    def row(self, after: bool) -> None:
        """Insert a row adjacent to the caret; row zero remains the header."""
        self._edit(
            lambda table, cursor: table.insertRows(
                table.cellAt(cursor).row() + int(after), 1
            )
        )

    def column(self, after: bool) -> None:
        """Insert a column adjacent to the caret."""
        self._edit(
            lambda table, cursor: table.insertColumns(
                table.cellAt(cursor).column() + int(after), 1
            )
        )

    def delete_row(self) -> None:
        """Remove the selected row; deleting the last row removes the table."""
        if (table := self.view.textCursor().currentTable()) and table.rows() == 1:
            self.delete()
        else:
            self._edit(
                lambda table, cursor: table.removeRows(table.cellAt(cursor).row(), 1)
            )

    def delete_column(self) -> None:
        """Remove the selected column, including a one-column table."""
        if (table := self.view.textCursor().currentTable()) and table.columns() == 1:
            self.delete()
        else:
            self._edit(
                lambda table, cursor: table.removeColumns(
                    table.cellAt(cursor).column(), 1
                )
            )

    def delete(self) -> None:
        """Delete one table as a single undoable local operation."""

        def remove(table: QTextTable, cursor: QTextCursor) -> None:
            cursor.setPosition(table.firstPosition() - 1)
            cursor.setPosition(
                table.lastPosition() + 1, QTextCursor.MoveMode.KeepAnchor
            )
            cursor.removeSelectedText()

        self._edit(remove)

    def align(self, alignment: Qt.AlignmentFlag) -> None:
        """Apply alignment to every cell in the active column."""

        def apply(table: QTextTable, cursor: QTextCursor) -> None:
            column = table.cellAt(cursor).column()
            for row in range(table.rows()):
                target = table.cellAt(row, column).firstCursorPosition()
                fmt = target.blockFormat()
                fmt.setAlignment(alignment)
                target.setBlockFormat(fmt)

        self._edit(apply)

    def toggle_strike(self) -> None:
        """Toggle inline strikethrough without changing a cell's other marks."""
        if (
            self.view.isReadOnly()
            or self.view._view_mode != "rich"
            or self.view.textCursor().currentTable() is None
        ):
            return
        cursor = self.view.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not cursor.charFormat().fontStrikeOut())
        if cursor.hasSelection():
            self._edit(lambda table, target: target.mergeCharFormat(fmt))
        else:
            self.view.mergeCurrentCharFormat(fmt)
        self.view.setFocus(Qt.FocusReason.OtherFocusReason)

    def key(self, event: QKeyEvent) -> bool:
        """Own cell navigation while keeping ordinary Tab non-mutating."""
        cursor = self.view.textCursor()
        table = cursor.currentTable()
        if table is None or self.view._view_mode != "rich":
            return False
        if event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
        ):
            return False
        key = event.key()
        if key not in (
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            return False
        cell = table.cellAt(cursor)
        backwards = key == Qt.Key.Key_Backtab or bool(
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )
        delta = -1 if backwards else 1
        index = cell.row() * table.columns() + cell.column() + delta
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = (cell.row() + 1) * table.columns() + cell.column()
        if 0 <= index < table.rows() * table.columns():
            cursor = table.cellAt(
                index // table.columns(), index % table.columns()
            ).firstCursorPosition()
        else:
            cursor.setPosition(
                table.firstPosition() - 1 if backwards else table.lastPosition() + 1
            )
        self.view.setTextCursor(cursor)
        event.accept()
        return True

    def paste(self, text: str) -> bool:
        """Project a pasted table through Source without flattening its structure."""
        if not has_table(text) or requires_source_mode(text):
            return False
        if self.view._view_mode != "source":
            self.view.toggle_view_mode()
        cursor = self.view.textCursor()
        source = self.view.toPlainText().encode("utf-16-le")
        before = source[: cursor.selectionStart() * 2].decode("utf-16-le")
        after = source[cursor.selectionEnd() * 2 :].decode("utf-16-le")
        if before and not before.endswith("\n\n"):
            text = "\n" * (2 - (len(before) - len(before.rstrip("\n")))) + text
        if after and not after.startswith("\n\n"):
            text += "\n" * (2 - (len(after) - len(after.lstrip("\n"))))
        self.view._insert_source_text(text)
        if not requires_source_mode(self.view.get_wiki_text()):
            self.view.toggle_view_mode()
        return True

    def paint(self, painter: QPainter) -> None:
        """Draw theme-owned table boundaries without creating document edits."""
        if self.view._view_mode != "rich":
            return
        boundary = QColor(ThemeManager().get_theme()["action_secondary_normal_border"])
        painter.setPen(QPen(boundary, 1))
        layout = self.view.document().documentLayout()
        if layout is None:
            return
        offset = QPointF(
            -self.view.horizontalScrollBar().value(),
            -self.view.verticalScrollBar().value(),
        )
        for table in tables(self.view):
            rect = layout.frameBoundingRect(table).translated(offset)
            painter.drawRect(rect)
            for row in range(1, table.rows()):
                painter.setPen(QPen(boundary, 2 if row == 1 else 1))
                block = table.cellAt(row, 0).firstCursorPosition().block()
                y = (
                    layout.blockBoundingRect(block).top()
                    + offset.y()
                    - table.format().cellPadding()
                )
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            for column in range(1, table.columns()):
                painter.setPen(QPen(boundary, 1))
                block = table.cellAt(0, column).firstCursorPosition().block()
                x = (
                    layout.blockBoundingRect(block).left()
                    + offset.x()
                    - table.format().cellPadding()
                )
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
