"""Compact Project Explorer control for session context tags."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.widgets.tag_chip_view import tag_color_for_theme


class ContextTagBar(QFrame):
    """Render context-tag state and emit user intents only."""

    edit_requested = Signal()
    enable_requested = Signal()
    disable_requested = Signal()
    review_requested = Signal()

    MAX_VISIBLE_CHIPS = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("contextTagBar")
        self.setAccessibleName("Context tags")
        self._state: dict[str, object] = {
            "tags": [],
            "active": False,
            "affected_count": 0,
            "history_count": 0,
        }

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        self.lbl_state = QLabel("Context Tags: Off")
        self.lbl_state.setObjectName("contextTagState")
        layout.addWidget(self.lbl_state)

        self._chip_host = QWidget()
        self._chip_layout = QHBoxLayout(self._chip_host)
        self._chip_layout.setContentsMargins(0, 0, 0, 0)
        self._chip_layout.setSpacing(3)
        layout.addWidget(self._chip_host, stretch=1)

        self.lbl_count = QLabel()
        layout.addWidget(self.lbl_count)

        self.btn_review = QPushButton("Review")
        self.btn_review.clicked.connect(self.review_requested.emit)
        layout.addWidget(self.btn_review)

        self.btn_enable = QPushButton("Enable")
        self.btn_enable.clicked.connect(self.enable_requested.emit)
        layout.addWidget(self.btn_enable)

        self.btn_edit = QPushButton("Set…")
        self.btn_edit.clicked.connect(self.edit_requested.emit)
        layout.addWidget(self.btn_edit)

        self.btn_disable = QPushButton("Disable")
        self.btn_disable.clicked.connect(self.disable_requested.emit)
        layout.addWidget(self.btn_disable)

        theme_manager = ThemeManager()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        self._on_theme_changed(theme_manager.get_theme())
        self.set_state(self._state)

    def set_state(self, state: dict[str, object]) -> None:
        """Render an immutable coordinator state snapshot."""
        raw_tags = state.get("tags", [])
        tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
        raw_count = state.get("affected_count", 0)
        affected = raw_count if isinstance(raw_count, int) else 0
        raw_history_count = state.get("history_count", 0)
        history_count = raw_history_count if isinstance(raw_history_count, int) else 0
        self._state = {
            "tags": tags,
            "active": bool(state.get("active", False)),
            "affected_count": affected,
            "history_count": history_count,
        }
        active = bool(self._state["active"])

        self.lbl_state.setText("Context Tags Active" if active else "Context Tags: Off")
        self.lbl_count.setText(f"{affected} item{'s' if affected != 1 else ''}")
        self.lbl_count.setVisible(affected > 0)
        self.btn_review.setText(f"Review ({affected})" if affected else "History")
        self.btn_review.setVisible(history_count > 0)
        self.btn_enable.setVisible(bool(tags) and not active)
        self.btn_disable.setVisible(active)
        self.btn_edit.setText("Change…" if tags else "Set…")
        self._rebuild_chips(tags)
        self._apply_style(ThemeManager().get_theme())

    def _rebuild_chips(self, tags: list[str]) -> None:
        while self._chip_layout.count():
            item = self._chip_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        theme = ThemeManager().get_theme()
        for tag in tags[: self.MAX_VISIBLE_CHIPS]:
            color = tag_color_for_theme(tag, theme)
            chip = QLabel(tag)
            chip.setToolTip(tag)
            chip.setStyleSheet(
                "QLabel {"
                f"color: {theme['text_main']};"
                f"background-color: rgba({color.red()}, {color.green()}, "
                f"{color.blue()}, 72);"
                f"border: 1px solid {color.name()};"
                "border-radius: 9px; padding: 1px 6px;"
                "}"
            )
            self._chip_layout.addWidget(chip)
        if len(tags) > self.MAX_VISIBLE_CHIPS:
            overflow = QLabel(f"+{len(tags) - self.MAX_VISIBLE_CHIPS}")
            overflow.setToolTip(", ".join(tags[self.MAX_VISIBLE_CHIPS :]))
            self._chip_layout.addWidget(overflow)
        self._chip_layout.addStretch(1)

    @Slot(dict)
    def _on_theme_changed(self, theme: dict[str, Any]) -> None:
        raw_tags = self._state["tags"]
        tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
        self._rebuild_chips(tags)
        self._apply_style(theme)

    def _apply_style(self, theme: dict[str, Any]) -> None:
        active = bool(self._state["active"])
        accent = theme["primary"] if active else theme["border"]
        background = theme["surface"]
        self.setStyleSheet(
            "QFrame#contextTagBar {"
            f"background-color: {background}; border: 2px solid {accent};"
            "border-radius: 4px;"
            "}"
            "QLabel#contextTagState {"
            f"color: {theme['text_main']}; font-weight: "
            f"{'bold' if active else 'normal'};"
            "}"
        )
