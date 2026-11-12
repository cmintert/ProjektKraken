"""Map table selections within structural cells, including repeated labels."""

from difflib import SequenceMatcher

from PySide6.QtGui import QTextCursor, QTextDocument, QTextTable

from src.core.markdown_content import parse_content
from src.core.markdown_extensions import WIKI_PATTERN


def _units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _text_positions(
    origin: str, destination: str, positions: list[int], *, cell: bool = False
) -> list[int]:
    # Cell-local matching retains repeated text; global fallback uses pruning.
    opcodes = SequenceMatcher(
        None, origin, destination, autojunk=not cell
    ).get_opcodes()
    result = []
    for position in positions:
        offset = len(origin.encode("utf-16-le")[: position * 2].decode("utf-16-le"))
        exact = [
            target + offset - start
            for tag, start, end, target, _ in opcodes
            if tag == "equal" and start <= offset <= end
        ]
        mapped = len(destination)
        if exact:
            mapped = max(exact) if position == min(positions) else min(exact)
        else:
            for _, start, end, target, target_end in opcodes:
                if start <= offset <= end:
                    mapped = (
                        target_end
                        if offset == end
                        else target + min(offset - start, target_end - target)
                    )
                    break
        result.append(_units(destination[:mapped]))
    return result


def _cell_spans(line: str) -> list[tuple[int, int]]:
    """Split source cells while protecting escaped and legacy wikilink pipes."""
    links = list(WIKI_PATTERN.finditer(line))
    edges = [-1]
    for index, character in enumerate(line):
        if character != "|" or any(
            link.start() <= index < link.end() for link in links
        ):
            continue
        prefix = line[:index]
        if (len(prefix) - len(prefix.rstrip("\\"))) % 2 == 0:
            edges.append(index)
    edges.append(len(line))
    spans = []
    for start, end in zip(edges, edges[1:], strict=False):
        start += 1
        while start < end and line[start].isspace():
            start += 1
        while end > start and line[end - 1].isspace():
            end -= 1
        spans.append((start, end))
    if line.lstrip().startswith("|"):
        spans.pop(0)
    if line.rstrip().endswith("|"):
        spans.pop()
    return spans


def map_table_selection(
    source: str, rich: QTextDocument, source_mode: bool, positions: list[int]
) -> list[int]:
    """Retain the selected cell identity before matching its inline spelling."""
    plain = rich.toPlainText()
    origin, destination = (source, plain) if source_mode else (plain, source)
    result = _text_positions(origin, destination, positions)
    ranges = [
        token.map
        for token in parse_content(source).tokens
        if token.type == "table_open" and token.map
    ]
    frames = [
        frame
        for frame in rich.rootFrame().childFrames()
        if isinstance(frame, QTextTable)
    ]
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    for table, (start, _) in zip(frames, ranges, strict=False):
        for row in range(table.rows()):
            line_number = start if row == 0 else start + row + 1
            spans = _cell_spans(lines[line_number])
            for column, (first, last) in enumerate(spans[: table.columns()]):
                cell = table.cellAt(row, column)
                cursor = cell.firstCursorPosition()
                rich_start = cursor.position()
                cursor.setPosition(cell.lastPosition(), QTextCursor.MoveMode.KeepAnchor)
                rich_text = cursor.selectedText().replace("\u2029", "\n")
                raw_start = offsets[line_number] + first
                source_start = _units(source[:raw_start])
                source_text = lines[line_number][first:last]
                local_origin, local_destination = (
                    (source_text, rich_text)
                    if source_mode
                    else (rich_text, source_text)
                )
                origin_start, target_start = (
                    (source_start, rich_start)
                    if source_mode
                    else (rich_start, source_start)
                )
                matching = [
                    i
                    for i, position in enumerate(positions)
                    if origin_start <= position <= origin_start + _units(local_origin)
                ]
                local = [positions[i] - origin_start for i in matching]
                mapped = _text_positions(
                    local_origin, local_destination, local, cell=True
                )
                for index, position in zip(matching, mapped, strict=True):
                    result[index] = target_start + position
    return result
