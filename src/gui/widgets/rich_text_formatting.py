"""In-place cleanup of imported rich-text presentation, retaining link metadata."""

from PySide6.QtGui import (
    QFont,
    QTextBlock,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)

from src.gui.editor_typography import EditorTypography


def body_character_format(
    original: QTextCharFormat, typography: EditorTypography
) -> QTextCharFormat:
    """Remove imported colors and emphasis without replacing anchor identity."""
    cleaned = QTextCharFormat(original)
    cleaned.clearForeground()
    cleaned.clearBackground()
    cleaned.setFontWeight(QFont.Weight.Normal)
    cleaned.setFontItalic(False)
    cleaned.setFontFamilies([typography.primary_font_family])
    cleaned.setFontPointSize(typography.body_size)
    return cleaned


def _clear_block(block: QTextBlock, typography: EditorTypography) -> None:
    """Restore paragraph presentation without changing lists or text structure."""
    cursor = QTextCursor(block)
    fmt = QTextBlockFormat(block.blockFormat())
    was_heading = fmt.headingLevel() > 0
    fmt.clearBackground()
    fmt.setHeadingLevel(0)
    top, bottom = typography.block_margins(0)
    fmt.setTopMargin(top)
    fmt.setBottomMargin(bottom)
    fmt.setLineHeight(
        typography.line_height_percent,
        QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
    )
    cursor.setBlockFormat(fmt)
    cursor.setBlockCharFormat(
        body_character_format(cursor.blockCharFormat(), typography)
    )
    if was_heading and block.length() > 1:
        # Heading typography belongs to the paragraph, even for partial selections.
        # Retain other inline properties outside the selected character range.
        body = QTextCharFormat()
        body.setFontWeight(QFont.Weight.Normal)
        body.setFontFamilies([typography.primary_font_family])
        body.setFontPointSize(typography.body_size)
        cursor.setPosition(
            block.position() + block.length() - 1, QTextCursor.MoveMode.KeepAnchor
        )
        cursor.mergeCharFormat(body)


def clear_rich_formatting(cursor: QTextCursor, typography: EditorTypography) -> None:
    """Clean a selection or current paragraph as one undoable document edit.

    Snapshot fragment formats before changing them: setting formats can merge or
    split the live fragment iterator. End-exclusive selection bounds prevent a
    selection ending at the next paragraph from modifying that paragraph.
    """
    start, end = cursor.selectionStart(), cursor.selectionEnd()
    if not cursor.hasSelection():
        start = cursor.block().position()
        end = start + cursor.block().length() - 1
    block = cursor.document().findBlock(start)
    blocks = []
    updates = []
    while block.isValid() and (block.position() < end or block.position() == start):
        blocks.append(block)
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid():
                left = max(start, fragment.position())
                right = min(end, fragment.position() + fragment.length())
                if left < right:
                    updates.append((left, right, fragment.charFormat()))
            iterator += 1
        block = block.next()

    edit = QTextCursor(cursor)
    edit.beginEditBlock()
    try:
        for block in blocks:
            _clear_block(block, typography)
        for left, right, fmt in updates:
            edit.setPosition(left)
            edit.setPosition(right, QTextCursor.MoveMode.KeepAnchor)
            edit.setCharFormat(body_character_format(fmt, typography))
    finally:
        edit.endEditBlock()
