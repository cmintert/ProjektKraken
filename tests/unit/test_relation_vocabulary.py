"""Configured wording through persistence, presentation and structured context."""

import json

import pytest

from src.core.entities import Entity
from src.core.relation_vocabulary import (
    filter_labels,
    parse_vocabulary,
    resolve_wording,
)
from src.gui.dialogs.graph_filter_dialog import GraphFilterDialog
from src.gui.widgets.connection_presentation import project_connections
from src.gui.widgets.graph_view.graph_builder import GraphBuilder
from src.gui.widgets.graph_view.graph_filter_bar import GraphFilterBar
from src.services.authoring_context_builder import (
    AuthoringContextBuilder,
    format_entity_authoring_context,
)
from src.services.db_service import DatabaseService
from src.services.relation_vocabulary_reader import read_vocabulary

pytestmark = pytest.mark.ci_fast

MARRIED = {
    "key": "married",
    "forward_label": "Spouse",
    "reverse_label": "Spouse",
    "description": "One marriage",
    "symmetric": True,
    "forward_template": "{source} is married to {target}.",
    "reverse_template": "{target} is married to {source}.",
}
ROW = {
    "id": "marriage",
    "rel_type": "married",
    "source_id": "a",
    "target_id": "b",
    "source_name": "Ada",
    "target_name": "Ben",
}


def vocabulary_json(*definitions):
    return json.dumps({"version": 1, "definitions": definitions})


def test_one_assertion_has_two_perspectives():
    vocabulary = parse_vocabulary(vocabulary_json(MARRIED))
    forward = project_connections(
        [ROW], [], "entity", "a", "Ada", vocabulary=vocabulary
    )
    reverse = project_connections(
        [], [ROW], "entity", "b", "Ben", vocabulary=vocabulary
    )
    assert forward[0].assertion == "Ada is married to Ben."
    assert reverse[0].assertion == "Ben is married to Ada."
    assert forward[0].snapshot == reverse[0].snapshot == ROW
    assert forward[0].timing == reverse[0].timing


@pytest.mark.parametrize(
    "template", ["{target.name}", "{target!r}", "{{target}}", "{x}"]
)
def test_unsupported_templates_keep_the_reverse_label(template):
    vocabulary = parse_vocabulary(
        vocabulary_json({**MARRIED, "reverse_template": template})
    )
    result = resolve_wording(ROW, vocabulary, incoming=True)
    assert result.sentence is None
    assert result.assertion == "Spouse Ada"
    assert result.relation_id == "marriage"


def test_raw_fallback_and_caption_collisions():
    assert resolve_wording(ROW, {}, incoming=True).assertion == "Ada → married → Ben"
    vocabulary = parse_vocabulary(
        vocabulary_json(MARRIED, {**MARRIED, "key": "civil_union"})
    )
    assert filter_labels(("married", "civil_union"), vocabulary) == {
        "married": "Spouse (married)",
        "civil_union": "Spouse (civil_union)",
    }
    assert parse_vocabulary(vocabulary_json(MARRIED, MARRIED)) == {}


def test_world_wording_leaves_system_and_unspecified_labels_in_place():
    vocabulary = parse_vocabulary(
        vocabulary_json({**MARRIED, "key": "related"}, {**MARRIED, "key": "mentions"})
    )
    assert vocabulary == {}
    assert resolve_wording({**ROW, "rel_type": "related"}, vocabulary).label == (
        "Connected — kind not specified"
    )
    assert resolve_wording({**ROW, "rel_type": "mentions"}, vocabulary).label == (
        "Reference (read-only)"
    )


def test_vocabulary_loads_in_read_only_world(tmp_path):
    path = str(tmp_path / "world.kraken")
    writable = DatabaseService(path)
    writable.connect()
    try:
        with writable.transaction() as connection:
            connection.execute(
                "INSERT INTO system_meta (key, value) VALUES (?, ?)",
                ("relation_vocabulary", vocabulary_json(MARRIED)),
            )
    finally:
        writable.close()
    readonly = DatabaseService(path, read_only=True)
    readonly.connect()
    try:
        connection = readonly.require_connection()
        assert read_vocabulary(connection)["married"]["forward_label"] == "Spouse"
        assert connection.total_changes == 0
    finally:
        readonly.close()


def test_context_reads_world_snapshot_and_keeps_canonical_fields(db_service):
    connection = db_service.require_connection()
    changes = connection.total_changes
    assert read_vocabulary(connection) == {}
    assert connection.total_changes == changes
    ada = Entity(name="Ada", type="Character")
    ben = Entity(name="<Ben>", type="Character")
    db_service.insert_entity(ada)
    db_service.insert_entity(ben)
    relation_id = db_service.insert_relation(ada.id, ben.id, "married")
    connection.execute(
        "INSERT INTO system_meta (key, value) VALUES (?, ?)",
        ("relation_vocabulary", vocabulary_json(MARRIED)),
    )
    context = AuthoringContextBuilder(db_service).build_entity_context(ben.id)
    relation = context.direct_relations[0]
    assert relation.to_dict()["display_text"] == "<Ben> is married to Ada."
    assert "<Ben> is married to Ada." in format_entity_authoring_context(context)
    assert (relation.id, relation.rel_type) == (relation_id, "married")
    assert (relation.source.id, relation.target.id) == (ada.id, ben.id)


def test_graph_wording_preserves_edge_identity_and_escapes_tooltip():
    edge = GraphBuilder.prepare_edge(
        {**ROW, "display_label": "<Spouse>", "validity_status": "possible"},
        "#112233",
        lexicon={"married": {"color": "#445566"}},
    )
    assert (edge["id"], edge["from"], edge["to"]) == ("marriage", "a", "b")
    assert edge["label"] == "<Spouse> (?)"
    assert "&lt;Spouse&gt;" in edge["title"]
    assert edge["color"] == "#445566"


def test_graph_filters_return_exact_type_after_caption_refresh(qtbot):
    labels = {"married": "Spouse (married)", "civil_union": "Spouse (civil_union)"}
    keys = list(labels)
    bar = GraphFilterBar()
    qtbot.addWidget(bar)
    bar.set_available_relation_types(keys)
    bar._rel_type_combo.setCurrentIndex(bar._rel_type_combo.findData("married"))
    bar.set_available_relation_types(keys, labels)
    assert bar._rel_type_combo.currentText() == labels["married"]
    assert bar.get_selected_relation_types() == ["married"]

    dialog = GraphFilterDialog(
        available_rel_types=keys,
        current_config={"rel_types": {"include": ["civil_union"]}},
        relation_labels=labels,
    )
    qtbot.addWidget(dialog)
    assert dialog.rel_filter_widget.list_include.item(0).text() == labels["civil_union"]
    assert dialog.get_filter_config()["rel_types"]["include"] == ["civil_union"]
