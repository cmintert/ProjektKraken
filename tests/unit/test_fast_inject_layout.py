from src.core.entities import Entity
from src.core.fast_inject import FastInjectManager, FastInjectTemplate


def test_apply_template_with_layout_no_existing_layout(tmp_path):
    """Test applying a template with a layout to an entity with no layout."""
    manager = FastInjectManager(tmp_path)

    target = Entity(name="Test", type="Character")
    assert "_sheet_layout" not in target.attributes

    template = FastInjectTemplate(
        name="LayoutTemplate",
        attributes={
            "NewAttr1": "val1",
            "NewAttr2": "val2",
            "_sheet_layout": [["NewAttr1", "NewAttr2"]],
        },
    )

    manager.apply_template(target, template)

    assert "NewAttr1" in target.attributes
    assert "_sheet_layout" in target.attributes
    assert target.attributes["_sheet_layout"] == [["NewAttr1", "NewAttr2"]]


def test_apply_template_merges_layout_with_overwrite(tmp_path):
    """Test appending template layout to existing layout, replacing existing items if overwrite=True."""
    manager = FastInjectManager(tmp_path)

    target = Entity(
        name="Test",
        type="Character",
        attributes={
            "Existing1": "v1",
            "Target2": "v2",
            "_sheet_layout": [["Existing1"], ["Target2"]],
        },
    )

    # Template will overwrite Target2 and bring its own layout
    template = FastInjectTemplate(
        name="T1",
        attributes={
            "Target2": "new_v2",
            "TemplateAttr": "v3",
            "_sheet_layout": [["TemplateAttr", "Target2"]],
        },
    )

    manager.apply_template(target, template, overwrite=True)

    # The existing Target2 on its own row should be removed, yielding to the appended row.
    assert target.attributes["_sheet_layout"] == [
        ["Existing1"],
        ["TemplateAttr", "Target2"],
    ]


def test_apply_template_merges_layout_without_overwrite(tmp_path):
    """Test appending layout where existing keys take precedence if overwrite=False."""
    manager = FastInjectManager(tmp_path)

    target = Entity(
        name="Test",
        type="Character",
        attributes={
            "Existing1": "v1",
            "ConflictAttr": "v2",
            "_sheet_layout": [["Existing1", "ConflictAttr"]],
        },
    )

    # Template provides ConflictAttr but overwrite=False, so the target keeps its own version
    template = FastInjectTemplate(
        name="T1",
        attributes={
            "ConflictAttr": "new_v2",  # won't be applied
            "NewAttr": "v3",
            "_sheet_layout": [
                ["NewAttr"],
                [{"type": "spacer", "weight": 1}, "ConflictAttr"],
            ],
        },
    )

    manager.apply_template(target, template, overwrite=False)

    # Because overwrite is False, ConflictAttr is kept in the existing layout (row 0).
    # The template's ConflictAttr element should be stripped from the appended layout.
    # Leaving `NewAttr` on its own row, and a row with just a spacer.
    # If the pruning logic strips out ConflictAttr, the spacer still exists, but let's see how our logic does it.

    result_layout = target.attributes["_sheet_layout"]
    assert ["Existing1", "ConflictAttr"] in result_layout
    # NewAttr row appended
    assert ["NewAttr"] in result_layout

    # And we expect the second appended row to just have a spacer, since ConflictAttr was pruned
    last_row = result_layout[-1]
    assert len(last_row) == 1
    assert last_row[0] == {"type": "spacer", "weight": 1}
