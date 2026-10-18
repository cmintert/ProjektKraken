"""Compose the shared browser and existing local draft owner."""

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout

from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.connections_overview import ConnectionsOverview
from src.gui.widgets.relation_authoring import RelationAuthoring


def install_connections(editor: Any, kind: str) -> None:
    """Wire existing editor intent at one shared presentation composition seam."""
    layout = QVBoxLayout(editor.tab_relations)
    StyleHelper.apply_no_margins(layout)
    overview = ConnectionsOverview(kind, editor.tab_relations)
    editor.connections = overview
    authoring = RelationAuthoring(editor)
    editor.relation_authoring = authoring
    overview.before_selection = authoring.prepare_selection_change
    overview.edit_requested.connect(authoring.refine)
    overview.connect_requested.connect(authoring.capture)
    overview.remove_requested.connect(editor._on_remove_relation_item)
    overview.navigate_requested.connect(editor.navigate_to_relation.emit)
    editor.btn_add_rel = overview.connect_button
    editor.btn_edit_rel = overview.edit_button
    editor.btn_remove_rel = overview.remove_button
    # Drop preparation remains visible in browse mode; it never saves on drop.
    layout.addWidget(authoring.drop_target)
    menu = authoring._more_actions_button
    menu.setParent(overview)
    if kind == "event":
        menu.menu().addAction("Add participant…", lambda: authoring.capture("involved"))
        menu.menu().addAction("Add location…", lambda: authoring.capture("located_at"))
    overview.add_secondary_actions(menu.menu())
    overview.header_actions.add_button(menu)
    splitter = QSplitter(Qt.Orientation.Vertical)
    splitter.setChildrenCollapsible(False)
    splitter.addWidget(overview)
    splitter.addWidget(authoring)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 1)
    layout.addWidget(splitter, 1)

    def opened() -> None:
        splitter.setSizes([max(80, splitter.height() // 2)] * 2)

    authoring.opened.connect(opened)
