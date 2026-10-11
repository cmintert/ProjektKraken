"""Read-only UI-GATE-01 measurement adapters and structured diagnostics."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass

import shiboken6
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QMenu,
    QRadioButton,
    QScrollArea,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionMenuItem,
    QStyleOptionTab,
    QTabBar,
    QTableView,
    QTableWidget,
    QToolBar,
    QToolButton,
    QWidget,
)

from src.gui.utils.action_label_metrics import action_label_geometry


@dataclass(frozen=True)
class LabelFailure:
    """An actionable presentation failure with reproducible geometry."""

    control: str
    text: str
    kind: str
    required: tuple[int, int]
    available: tuple[int, int, int, int]

    def to_dict(self) -> dict:
        """Serialize without transferring live Qt objects."""
        return asdict(self)


def control_path(widget: QWidget, root: QWidget) -> str:
    """Identify a control by ancestry and sibling index when unnamed."""
    parts = []
    current: QWidget | None = widget
    while current is not None:
        parent = current.parentWidget()
        index = parent.children().index(current) if parent is not None else 0
        parts.append(current.objectName() or f"{type(current).__name__}[{index}]")
        if current is root:
            break
        current = parent
    return "/".join(reversed(parts))


def _fit_failures(
    path: str, text: str, required: QSize, available: QRect
) -> list[LabelFailure]:
    kinds = []
    if required.width() > available.width():
        kinds.append("horizontal_clipping")
    if required.height() > available.height():
        kinds.append("vertical_clipping")
    return [
        LabelFailure(path, text, kind, required.toTuple(), available.getRect())
        for kind in kinds
    ]


def button_failures(button: QAbstractButton, root: QWidget) -> list[LabelFailure]:
    """Check real button labels; icon conventions require a named audit record."""
    path = control_path(button, root)
    if not button.text() or (
        isinstance(button, QToolButton)
        and button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        and not button.icon().isNull()
    ):
        named_action = (
            isinstance(button, QToolButton)
            and button.defaultAction() is not None
            and bool(button.defaultAction().text())
        )
        if button.accessibleName() or named_action:
            return []
        return [
            LabelFailure(
                path, "", "missing_accessible_name", (0, 0), button.rect().getRect()
            )
        ]
    try:
        adapter = getattr(button, "label_geometry", None)
        geometry = adapter() if callable(adapter) else action_label_geometry(button)
    except TypeError:
        return [
            LabelFailure(
                path, button.text(), "unknown_adapter", (0, 0), button.rect().getRect()
            )
        ]
    if not geometry.fits and _native_toolbar_route(button, root):
        return []
    return _fit_failures(path, geometry.text, geometry.required, geometry.available)


def combo_failures(combo: QComboBox, root: QWidget) -> list[LabelFailure]:
    """Measure selected command/mode wording, excluding authored data selectors."""
    if combo.property("actionLabelDataValue") or combo.isEditable():
        return []
    text = combo.currentText() or combo.placeholderText()
    if not text:
        return []
    adapter = getattr(combo, "label_geometry", None)
    if callable(adapter):
        geometry = adapter()
        return _fit_failures(
            control_path(combo, root),
            geometry.text,
            geometry.required,
            geometry.available,
        )
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    available = combo.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox,
        option,
        QStyle.SubControl.SC_ComboBoxEditField,
        combo,
    )
    return _fit_failures(
        control_path(combo, root),
        combo.currentText(),
        combo.fontMetrics().size(Qt.TextFlag.TextSingleLine, text),
        available,
    )


def tab_failures(bar: QTabBar, root: QWidget) -> list[LabelFailure]:
    """Check tabs against style content size, or a labeled sections menu."""
    parent = bar.parentWidget()
    overflow = getattr(parent, "overflow_button", None)
    if overflow is not None and overflow.isVisibleTo(root):
        menu = overflow.menu()
        if menu is not None:
            menu.aboutToShow.emit()
            wording = {action.text() for action in menu.actions()}
            if all(bar.tabText(index) in wording for index in range(bar.count())):
                return menu_failures(menu)
    failures = []
    for index in range(bar.count()):
        option = QStyleOptionTab()
        bar.initStyleOption(option, index)
        required = bar.fontMetrics().size(
            Qt.TextFlag.TextShowMnemonic, bar.tabText(index)
        )
        required = bar.style().sizeFromContents(
            QStyle.ContentsType.CT_TabBarTab, option, required, bar
        )
        failures.extend(
            _fit_failures(
                f"{control_path(bar, root)}/tab[{index}]",
                bar.tabText(index),
                required,
                bar.tabRect(index),
            )
        )
    return failures


def menu_failures(menu: QMenu, expected: list[str] | None = None) -> list[LabelFailure]:
    """Check populated/open menus, including full command wording and shortcuts."""
    with _opened_menu(menu):
        return _measure_menu(menu, expected)


@contextmanager
def _opened_menu(menu: QMenu) -> Iterator[None]:
    """Use final native popup geometry and restore the original focus owner."""
    visible = menu.isVisible()
    focused = QApplication.focusWidget()
    if not visible:
        menu.popup(menu.mapToGlobal(QPoint()))
        QApplication.processEvents()
    try:
        yield
    finally:
        if not visible:
            menu.hide()
        if focused is not None and shiboken6.isValid(focused):
            focused.setFocus()


def _measure_menu(menu: QMenu, expected: list[str] | None) -> list[LabelFailure]:
    """Measure action rows after Qt finalizes font and shortcut columns."""
    failures = []
    for index, action in enumerate(menu.actions()):
        if action.isSeparator() or not action.isVisible():
            continue
        option = QStyleOptionMenuItem()
        menu.initStyleOption(option, action)
        text = action.text()
        path = f"{menu.objectName() or 'QMenu'}/action[{index}]"
        if not text.strip():
            failures.append(
                LabelFailure(
                    path,
                    text,
                    "missing_action_name",
                    (0, 0),
                    menu.actionGeometry(action).getRect(),
                )
            )
        label, _, shortcut = option.text.partition("\t")
        metrics = QFontMetrics(option.font)
        required = metrics.size(Qt.TextFlag.TextShowMnemonic, label)
        required.setWidth(required.width() + metrics.horizontalAdvance(shortcut))
        required = menu.style().sizeFromContents(
            QStyle.ContentsType.CT_MenuItem, option, required, menu
        )
        failures.extend(
            _fit_failures(
                path,
                text,
                required,
                menu.actionGeometry(action).intersected(menu.rect()),
            )
        )
        if expected is not None and (index >= len(expected) or text != expected[index]):
            failures.append(
                LabelFailure(
                    path,
                    text,
                    "changed_wording",
                    required.toTuple(),
                    menu.actionGeometry(action).getRect(),
                )
            )
    return failures


def audit_widget(root: QWidget) -> list[LabelFailure]:
    """Inspect visible controls, clipping ancestors and actionable collisions."""
    failures: list[LabelFailure] = []
    controls = [root, *root.findChildren(QWidget)]
    actionable = []
    for widget in controls:
        if not widget.isVisibleTo(root):
            continue
        if isinstance(widget, QAbstractButton):
            # Native toolbar extension/tab arrows are infrastructure, whose
            # command destinations are audited separately.
            if widget.objectName() in (
                "qt_toolbar_ext_button",
                "ScrollLeftButton",
                "ScrollRightButton",
            ):
                continue
            if type(widget).__name__ == "QAbstractButton" and isinstance(
                widget.parentWidget(), QTableView
            ):
                # Native select-all table corner; no command wording is painted.
                continue
            failures.extend(button_failures(widget, root))
            actionable.append(widget)
        elif isinstance(widget, QComboBox):
            if widget.isEditable() or widget.property("actionLabelDataValue"):
                continue
            failures.extend(combo_failures(widget, root))
            actionable.append(widget)
        elif isinstance(widget, QTabBar):
            failures.extend(tab_failures(widget, root))
    for widget in actionable:
        failures.extend(_ancestor_failures(widget, root))
    failures.extend(_collisions(actionable, root))
    for toolbar in root.findChildren(QToolBar):
        # A native extension may be cramped. Inspect its real populated menu
        # rather than accepting hidden actions without a destination.
        extension = toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
        if extension is not None and extension.isVisibleTo(root) and extension.menu():
            failures.extend(menu_failures(extension.menu()))
    return failures


def _scroll_routes(widget: QWidget, root: QWidget) -> list[QScrollArea | QTableWidget]:
    scroll_areas = []
    parent = widget.parentWidget()
    while parent is not None and parent is not root:
        if isinstance(parent, (QScrollArea, QTableWidget)):
            scroll_areas.append(parent)
        parent = parent.parentWidget()
    return scroll_areas


def _reveal_table_cell(table: QTableWidget, widget: QWidget) -> None:
    for row in range(table.rowCount()):
        for column in range(table.columnCount()):
            cell = table.cellWidget(row, column)
            if cell is widget or (cell is not None and cell.isAncestorOf(widget)):
                table.scrollTo(table.model().index(row, column))
                return


def _label_bounds(widget: QWidget) -> QRect:
    adapter = getattr(widget, "label_geometry", None)
    if callable(adapter):
        geometry = adapter()
        result = QRect(QPoint(), geometry.required)
        result.moveCenter(geometry.available.center())
        if isinstance(widget, (QCheckBox, QRadioButton)):
            result.moveLeft(geometry.available.left())
        return result
    if isinstance(widget, QAbstractButton) and widget.text():
        label = widget.fontMetrics().size(Qt.TextFlag.TextShowMnemonic, widget.text())
    elif isinstance(widget, QComboBox):
        label = widget.fontMetrics().size(
            Qt.TextFlag.TextSingleLine, widget.currentText() or widget.placeholderText()
        )
    else:
        return widget.rect()
    result = QRect(QPoint(), label)
    result.moveCenter(widget.rect().center())
    return result


def _ancestor_failures(widget: QWidget, root: QWidget) -> list[LabelFailure]:
    """Distinguish inaccessible clipping from ordinary recoverable scrolling."""
    if (
        isinstance(widget, QComboBox)
        and not widget.currentText()
        and not widget.placeholderText()
    ):
        return []
    positions = [
        (area, area.horizontalScrollBar().value(), area.verticalScrollBar().value())
        for area in _scroll_routes(widget, root)
    ]
    for area, _, _ in positions:
        if isinstance(area, QScrollArea):
            # Reveal the painted wording, rather than the centre of an
            # expanding control whose unused width may exceed the viewport.
            label = _label_bounds(widget)
            centre = widget.mapTo(area.widget(), label.center())
            area.ensureVisible(
                centre.x(), centre.y(), label.width() // 2 + 1, label.height() // 2 + 1
            )
        else:
            _reveal_table_cell(area, widget)
    try:
        if positions:
            QApplication.processEvents()
        visible = widget.visibleRegion().boundingRect()
        if not widget.isVisibleTo(root) or visible.contains(_label_bounds(widget)):
            return []
        if _native_toolbar_route(widget, root):
            return []
        return [
            LabelFailure(
                control_path(widget, root),
                getattr(widget, "text", lambda: "")(),
                "ancestor_clipping",
                widget.size().toTuple(),
                visible.getRect(),
            )
        ]
    finally:
        for area, horizontal, vertical in positions:
            area.horizontalScrollBar().setValue(horizontal)
            area.verticalScrollBar().setValue(vertical)
        if positions:
            QApplication.processEvents()


def _native_toolbar_route(widget: QWidget, root: QWidget) -> bool:
    """Accept clipped native toolbar tools only with a real complete menu route."""
    if not isinstance(widget, QToolButton) or widget.defaultAction() is None:
        return False
    parent = widget.parentWidget()
    while parent is not None and parent is not root:
        if isinstance(parent, QToolBar):
            extension = parent.findChild(QToolButton, "qt_toolbar_ext_button")
            menu = extension.menu() if extension is not None else None
            if menu is not None and extension.isVisibleTo(root):
                if (
                    widget.defaultAction() in menu.actions()
                    and widget.defaultAction().text()
                ):
                    return True
            owner = parent.parentWidget()
            for button in owner.findChildren(QToolButton) if owner is not None else []:
                menu = button.menu()
                if (
                    button.property("actionLabelOverflowRoute")
                    and button.isVisibleTo(root)
                    and menu is not None
                ):
                    if (
                        widget.defaultAction() in menu.actions()
                        and widget.defaultAction().text()
                    ):
                        return True
        parent = parent.parentWidget()
    return False


def _collisions(controls: list[QWidget], root: QWidget) -> list[LabelFailure]:
    failures = []
    for index, first in enumerate(controls):
        first_rect = (
            first.visibleRegion().boundingRect().translated(first.mapTo(root, QPoint()))
        )
        for second in controls[index + 1 :]:
            if first.isAncestorOf(second) or second.isAncestorOf(first):
                continue
            second_rect = (
                second.visibleRegion()
                .boundingRect()
                .translated(second.mapTo(root, QPoint()))
            )
            overlap = first_rect.intersected(second_rect)
            first_label = _label_bounds(first).translated(first.mapTo(root, QPoint()))
            second_label = _label_bounds(second).translated(
                second.mapTo(root, QPoint())
            )
            if (
                first_label.intersected(second_rect).isEmpty()
                and second_label.intersected(first_rect).isEmpty()
            ):
                continue
            if not overlap.isEmpty():
                failures.append(
                    LabelFailure(
                        control_path(first, root),
                        getattr(first, "text", lambda: "")(),
                        f"overlap:{control_path(second, root)}",
                        first.size().toTuple(),
                        overlap.getRect(),
                    )
                )
    return failures
