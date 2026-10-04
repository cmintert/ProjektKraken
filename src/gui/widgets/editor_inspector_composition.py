"""Canonical inspector destinations assembled from existing live sections."""

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QAbstractButton,
    QFormLayout,
    QLabel,
    QSizePolicy,
    QTabWidget,
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
        context_layout = QVBoxLayout(context_container)
        StyleHelper.apply_no_margins(context_layout)
        context_layout.addWidget(content.context_disclosure)
        context_layout.addWidget(self.context_home)
        content.overview_form.addRow(context_container)
        self.context_home.hide()
        # DisclosureButton is supplied by EditorPresentation to avoid a cycle.
        content.context_disclosure.toggled.connect(self.context_home.setVisible)
        content.context_renderer.set_embedded(True)
        self.context_home.detached_changed.connect(
            lambda detached: content.context_renderer.set_embedded(not detached)
        )
        self.context_home.detached_changed.connect(
            lambda detached: content.context_disclosure.setText(
                "World context (open in another pane)"
                if detached
                else "World context (read-only)"
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
