"""Tests for the compact Event Context inspector."""

from PySide6.QtCore import Qt, QUrl

from src.core.authoring_context import (
    ContextAttachment,
    ContextAttribute,
    ContextCoAppearance,
    ContextEvent,
    ContextEventAppearance,
    ContextItem,
    ContextMapAppearance,
    ContextRelation,
    ContextSharedAssociation,
    ContextTag,
    EntityAuthoringContext,
    EventAuthoringContext,
)
from src.core.theme_manager import ThemeManager
from src.gui.widgets.authoring_context_widget import AuthoringContextWidget


def test_context_links_and_more_control_follow_active_theme(qtbot) -> None:
    widget = AuthoringContextWidget()
    qtbot.addWidget(widget)
    context = EventAuthoringContext(
        event_id="event-id",
        context_date=12.0,
        participants=(ContextItem("person-id", "entity", "Ada"),),
        mentions=(ContextItem("mention-id", "entity", "Cipher"),),
        previous_events=(ContextEvent("before-id", "Before", 11.0, "generic"),),
    )

    widget.set_context(context, date_label="Year 1")

    theme = ThemeManager().get_theme()
    document_css = widget.primary_view.document().defaultStyleSheet()
    assert theme["accent_secondary"] in document_css
    assert theme["primary"] in document_css
    assert theme["text_main"] in widget.primary_view.styleSheet()
    assert theme["surface"] in widget.scroll_area.styleSheet()
    assert theme["surface"] in widget.scroll_area.viewport().styleSheet()
    assert theme["surface"] in widget.scroll_content.styleSheet()
    assert theme["surface"] in widget.primary_view.styleSheet()
    assert widget.more_button.styleSheet()
    assert widget.more_button.isVisibleTo(widget)
    assert (
        widget.primary_view.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert widget.primary_view.height() >= int(
        widget.primary_view.document().size().height()
    )


def test_context_link_emits_target_id(qtbot) -> None:
    widget = AuthoringContextWidget()
    qtbot.addWidget(widget)
    with qtbot.waitSignal(widget.navigate_requested) as signal:
        widget.primary_view.setHtml(
            '<a href="kraken://e80d3e34-24a5-4d73-83a3-c551100b8372">Event</a>'
        )
        widget.primary_view.anchorClicked.emit(
            QUrl("kraken://e80d3e34-24a5-4d73-83a3-c551100b8372")
        )

    assert signal.args == ["e80d3e34-24a5-4d73-83a3-c551100b8372"]


def test_context_map_and_attachment_links_emit_typed_targets(qtbot) -> None:
    widget = AuthoringContextWidget(object_label="Entity")
    qtbot.addWidget(widget)
    with qtbot.waitSignal(widget.map_requested) as map_signal:
        widget.primary_view.anchorClicked.emit(QUrl("kraken-map://map-id"))
    with qtbot.waitSignal(widget.attachment_requested) as attachment_signal:
        widget.more_view.anchorClicked.emit(
            QUrl("kraken-attachment://attachment-id")
        )

    assert map_signal.args == ["map-id"]
    assert attachment_signal.args == ["attachment-id"]


def test_entity_context_primary_and_more_expose_every_section(qtbot) -> None:
    widget = AuthoringContextWidget(object_label="Entity")
    qtbot.addWidget(widget)
    root = ContextItem("root", "entity", "Ada")
    ally = ContextItem("ally", "entity", "Bram")
    context = EntityAuthoringContext(
        entity_id="root",
        attributes=(ContextAttribute("Role", "Navigator"),),
        tags=(ContextTag("tag", "Scholar"),),
        event_appearances=(
            ContextEventAppearance(
                ContextEvent("event", "Arrival", 10.0, "generic"),
                ("involved",),
            ),
        ),
        mentions=(ContextEvent("mention", "Rumour", 20.0, "generic"),),
        direct_relations=(
            ContextRelation("rel", root, ally, "knows", 0, "persistent"),
        ),
        temporal_history=(
            ContextRelation(
                "history", root, ally, "served", 0, "interval", 2.0, 4.0
            ),
        ),
        map_appearances=(ContextMapAppearance("map", "Coast", "point"),),
        linked_references=(
            ContextRelation("link", root, ally, "mentions", 0, "persistent"),
        ),
        co_appearances=(
            ContextCoAppearance(
                ally,
                (ContextEvent("shared", "Council", 5.0, "generic"),),
                1,
            ),
        ),
        shared_tags=(ContextSharedAssociation(ally, ("Scholar",)),),
        shared_maps=(ContextSharedAssociation(ally, ("Coast",)),),
        attachments=(ContextAttachment("image", "Portrait at the docks"),),
        omitted_counts=(("mentions", 2),),
    )

    widget.set_entity_context(context)

    primary = widget.primary_view.toPlainText()
    more = widget.more_view.toPlainText()
    assert "Role: Navigator" in primary
    assert "Scholar" in primary
    assert "Arrival" in primary
    assert "Placed on Coast" in primary
    assert "Rumour" in more
    assert "served" in more
    assert "Council" in more
    assert "Portrait at the docks" in more
    assert "Also placed on maps" in more
    assert "2 additional mentions omitted" in more
