"""Canonical inspector destinations assembled from existing live sections."""

from dataclasses import dataclass
from math import ceil

import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QFormLayout,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.authoring_context_widget import AuthoringContextWidget
from src.gui.widgets.inspector_section import AuxiliarySectionHome
from src.gui.widgets.splitter_tab_inspector import SplitterTabInspector


@dataclass
class InspectorContent:
    """Narrow presentation inputs; no editor, application or storage dependency."""

    overview: QWidget
    overview_form: QFormLayout
    context: QWidget
    context_renderer: AuthoringContextWidget
    context_disclosure: QAbstractButton
    linked_events: QWidget | None
    map_links: QWidget
    tags: QWidget
    connections: QWidget
    fields: QWidget
    sheet: QWidget
    media: QWidget


class EditorInspectorComposition:
    """Group the seven existing sections without rebuilding their contents."""

    def __init__(
        self, inspector: SplitterTabInspector, content: InspectorContent
    ) -> None:
        """Compose four primary destinations and two optional split sections."""
        for section in (
            content.overview,
            content.context,
            content.tags,
            content.connections,
            content.fields,
            content.sheet,
            content.media,
        ):
            inspector.remove_tab(section)

        self.details = QWidget(inspector)
        layout = QVBoxLayout(self.details)
        StyleHelper.apply_compact_spacing(layout)
        layout.addWidget(QLabel("Tags"))
        content.tags.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(content.tags)
        self.details_views = QTabWidget()
        self.details_views.setAccessibleName("Custom fields presentation")
        self.details_views.addTab(content.fields, "Fields")
        self.sheet_home = AuxiliarySectionHome(content.sheet, "Sheet")
        self.details_views.addTab(self.sheet_home, "Sheet")
        layout.addWidget(self.details_views, 1)
        self.context_home = AuxiliarySectionHome(content.context, "World context")
        context_container = QWidget()
        self.history_container = context_container
        context_container.setObjectName("InspectorSupportingInformation")
        context_layout = QVBoxLayout(context_container)
        StyleHelper.apply_no_margins(context_layout)
        context_layout.addWidget(content.context_disclosure)
        self.history_caption = QLabel(
            "Read-only information: linked events, map layer links and known world facts."
        )
        self.history_caption.setObjectName("InspectorSupportCaption")
        self.history_caption.setWordWrap(True)
        content.context_disclosure.setAccessibleDescription(self.history_caption.text())
        context_layout.addWidget(self.history_caption)
        self.history_body = QWidget()
        history_layout = QVBoxLayout(self.history_body)
        StyleHelper.apply_no_margins(history_layout)
        if content.linked_events is not None:
            self._fit_linked_events(content.linked_events)
            self._add_information_section(
                history_layout, "Linked events", content.linked_events
            )
        self._add_information_section(
            history_layout, "Map layer links", content.map_links
        )
        self._add_information_section(
            history_layout, "World context", self.context_home
        )
        context_layout.addWidget(self.history_body)
        content.overview_form.addRow(context_container)
        self.history_body.hide()
        # The supporting header is supplied by EditorPresentation to avoid a cycle.
        content.context_disclosure.toggled.connect(self.history_body.setVisible)
        context_container.setStyleSheet(StyleHelper.get_inspector_support_style())
        content.context_renderer.set_embedded(True)
        self.context_home.detached_changed.connect(
            lambda detached: content.context_renderer.set_embedded(not detached)
        )
        self.context_home.detached_changed.connect(
            lambda detached: self.history_caption.setText(
                "Read-only information: linked events, map layer links and known world facts."
                + (" World context is open in another pane." if detached else "")
            )
        )
        self.sheet_home.detached_changed.connect(
            lambda detached: self.details_views.setTabText(
                1, "Sheet (split)" if detached else "Sheet"
            )
        )
        for widget, title, section_id, tooltip in (
            (
                content.overview,
                "Overview",
                "overview",
                "Description, time, history and writing support",
            ),
            (
                content.connections,
                "Connections",
                "connections",
                "Authored relationships, participants and locations",
            ),
            (
                self.details,
                "Details",
                "details",
                "Tags and custom fields, with an optional Sheet view",
            ),
            (content.media, "Media", "media", "Images, attachments and captions"),
        ):
            inspector.add_tab(widget, title, tooltip, section_id=section_id)
        content.tags.show()
        content.fields.show()
        inspector.register_auxiliary(
            "world_context",
            self.context_home,
            "overview",
            lambda: content.context_disclosure.setChecked(True),
        )
        inspector.register_auxiliary(
            "sheet",
            self.sheet_home,
            "details",
            lambda: self.details_views.setCurrentIndex(1),
        )
        inspector.activate_section_id("overview")

    @staticmethod
    def _fit_linked_events(widget: QWidget) -> None:
        """Let Overview scroll the existing read-only history document."""
        view = widget.findChild(QTextEdit)
        assert view is not None and view.isReadOnly()
        view.setMinimumHeight(0)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        def fit() -> None:
            if shiboken6.isValid(view):
                view.setFixedHeight(max(32, ceil(view.document().size().height()) + 12))

        view.document().documentLayout().documentSizeChanged.connect(
            lambda _size: fit()
        )
        fit()

    @staticmethod
    def _add_information_section(
        layout: QVBoxLayout, title: str, widget: QWidget
    ) -> None:
        """Add a non-interactive heading above the existing read-only widget."""
        label = QLabel(title)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)
        layout.addWidget(widget)
        widget.show()
