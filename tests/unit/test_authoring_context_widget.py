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


def test_event_previews_keep_nearest_neighbors_visible(qtbot) -> None:
    widget = AuthoringContextWidget()
    qtbot.addWidget(widget)
    widget.set_context(
        EventAuthoringContext(
            event_id="now",
            context_date=10,
            previous_events=tuple(
                ContextEvent(str(i), f"Before {i}", i, "generic") for i in range(5)
            ),
            next_events=tuple(
                ContextEvent(str(i), f"After {i}", i, "generic") for i in range(11, 16)
            ),
        )
    )
    earlier = widget.sections["Earlier Events"].browser.toPlainText()
    later = widget.sections["Later Events"].browser.toPlainText()
    assert earlier.index("Before 4") < earlier.index("Before 3")
    assert "Before 0" not in earlier
    assert "After 11" in later
    assert "After 15" not in later
    widget.more_button.setChecked(True)
    assert "Before 0" in widget.sections["Earlier Events"].browser.toPlainText()
    assert "After 15" in widget.sections["Later Events"].browser.toPlainText()


def test_local_and_global_disclosures_reveal_loaded_rows_only(qtbot) -> None:
    widget = AuthoringContextWidget(object_label="Entity")
    qtbot.addWidget(widget)
    context = EntityAuthoringContext(
        "root",
        tags=tuple(ContextTag(str(i), f"Tag {i}") for i in range(8)),
        mentions=tuple(
            ContextEvent(str(i), f"Mention {i}", float(i), "generic") for i in range(5)
        ),
        omitted_counts=(("mentions", 20),),
    )
    before = context.to_dict()
    widget.set_entity_context(context)
    widget.show()
    attributes = widget.sections["Tags"]
    tags = widget.sections["Mentioned in Events"]
    assert attributes.heading.text() == "Tags (8)"
    assert "Tag 2" in attributes.browser.toPlainText()
    assert "Tag 3" not in attributes.browser.toPlainText()
    attributes.disclosure.setFocus()
    qtbot.keyClick(attributes.disclosure, Qt.Key.Key_Space)
    assert "Tag 7" in attributes.browser.toPlainText()
    assert "Mention 4" not in tags.browser.toPlainText()
    widget.set_loading()
    widget.set_entity_context(context)
    assert widget.sections["Tags"] is attributes
    assert attributes.disclosure.isChecked()
    assert not tags.disclosure.isChecked()
    qtbot.mouseClick(widget.more_button, Qt.MouseButton.LeftButton)
    assert "Mention 4" in tags.browser.toPlainText()
    assert widget.more_button.text() == "Collapse all"
    qtbot.mouseClick(widget.more_button, Qt.MouseButton.LeftButton)
    assert "Tag 3" not in attributes.browser.toPlainText()
    limits = widget.sections["Not included in this snapshot"]
    assert "20 additional mentions omitted" in limits.browser.toPlainText()
    assert context.to_dict() == before


def test_relation_rows_separate_timing_sources_and_state_changes(qtbot) -> None:
    widget = AuthoringContextWidget(object_label="Entity")
    qtbot.addWidget(widget)
    ruler = ContextItem("ruler", "entity", "Queen Mara")
    kingdom = ContextItem("kingdom", "entity", "Ashford")
    source = ContextItem("succession", "event", "Succession")
    relation = ContextRelation(
        "rules",
        ruler,
        kingdom,
        "rules",
        0,
        "interval",
        temporal_summary="Not active at the playhead; ends: Succession",
        temporal_evidence={"events": [{"id": source.id, "name": source.name}]},
    )
    widget.set_entity_context(
        EntityAuthoringContext(
            "kingdom",
            temporal_history=(
                relation,
                ContextRelation(
                    "state", source, kingdom, "changes_state", 0, "interval"
                ),
            ),
        )
    )
    history = widget.sections["Temporal history"].browser
    assert "Queen Mara → rules → Ashford\nNot active" in history.toPlainText()
    assert "changes_state" not in history.toPlainText()
    assert "Recorded state changes · Temporal history" in widget.sections
    colors = {}
    block = history.document().begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            fmt = fragment.charFormat()
            if fmt.isAnchor():
                colors[fmt.anchorHref()] = fmt.foreground().color().name().lower()
            iterator += 1
        block = block.next()
    theme = ThemeManager().get_theme()
    assert colors["kraken://ruler"] == theme["link_entity"].lower()
    assert colors["kraken://succession"] == theme["link_event"].lower()
    with qtbot.waitSignal(widget.navigate_requested) as signal:
        history.anchorClicked.emit(QUrl("kraken://succession"))
    assert signal.args == ["succession"]


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
    assert theme["link_neutral"] in document_css
    assert theme["primary"] in document_css
    assert theme["text_main"] in widget.primary_view.styleSheet()
    assert theme["surface"] in widget.scroll_area.styleSheet()
    assert theme["surface"] in widget.scroll_area.viewport().styleSheet()
    assert theme["surface"] in widget.scroll_content.styleSheet()
    assert theme["surface"] in widget.primary_view.styleSheet()
    assert widget.more_button.styleSheet()
    assert widget.more_button.isHidden()
    assert widget.sections["People & places"].heading.text() == "People & places (1)"
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
        widget.primary_view.anchorClicked.emit(
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
            ContextRelation("history", root, ally, "served", 0, "interval", 2.0, 4.0),
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

    primary = "\n".join(s.browser.toPlainText() for s in widget.sections.values())
    more = primary
    assert "Role: Navigator" not in primary
    assert "Scholar" in primary
    assert "Arrival" in primary
    assert "Placed on Coast" in primary
    assert "Rumour" in more
    assert "served" in more
    assert "Council" in more
    assert "Portrait at the docks" in more
    assert "Also placed on maps" in widget.sections
    assert "2 additional mentions omitted" in more


def test_narrow_context_document_wraps_and_same_item_retains_scroll(qtbot):
    widget = AuthoringContextWidget(object_label="Entity")
    qtbot.addWidget(widget)
    widget.resize(360, 220)
    context = EntityAuthoringContext(
        "person",
        tags=tuple(
            ContextTag(str(i), f"Long readable classification {i} " * 4)
            for i in range(24)
        ),
    )
    widget.set_entity_context(context)
    widget.more_button.setChecked(True)
    widget.show()
    qtbot.wait(20)
    assert (
        widget.sections["Tags"].browser.document().textWidth()
        <= widget.sections["Tags"].browser.viewport().width()
    )
    scrollbar = widget.scroll_area.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(100)
    widget.set_loading()
    widget.set_entity_context(context)
    qtbot.wait(20)
    assert scrollbar.value() == 100
    assert widget.more_button.isChecked()
