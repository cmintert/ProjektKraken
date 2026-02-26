from src.gui.dialogs.create_template_dialog import CreateTemplateDialog


def test_create_template_dialog_layout_pruning_checked(qtbot):
    """Test that source_layout is pruned and saved when checked."""
    source_attributes = {"Strength": 10, "Intelligence": 12, "Dexterity": 14}
    source_layout = [
        ["Strength", "Intelligence"],
        [{"type": "spacer", "weight": 1}, "Dexterity"],
    ]

    dlg = CreateTemplateDialog(
        source_tags=[],
        source_attributes=source_attributes,
        source_layout=source_layout,
    )
    qtbot.addWidget(dlg)

    # Uncheck 'Intelligence'
    dlg.attr_checks["Intelligence"].setChecked(False)

    # Check that layout checkbox exists and is checked by default
    assert hasattr(dlg, "chk_layout")
    assert dlg.chk_layout.isChecked()

    dlg._on_save()

    # Resulting attributes should lack Intelligence
    assert "Intelligence" not in dlg.result_data["selected_attributes"]

    # Resulting layout should lack Intelligence
    resulting_layout = dlg.result_data["selected_attributes"].get("_sheet_layout")
    assert resulting_layout is not None
    assert resulting_layout == [
        ["Strength"],
        [{"type": "spacer", "weight": 1}, "Dexterity"],
    ]


def test_create_template_dialog_layout_pruning_unchecked(qtbot):
    """Test that source_layout is NOT saved when layout checkbox is unchecked."""
    source_attributes = {"Strength": 10}
    source_layout = [["Strength"]]

    dlg = CreateTemplateDialog(
        source_tags=[],
        source_attributes=source_attributes,
        source_layout=source_layout,
    )
    qtbot.addWidget(dlg)

    dlg.chk_layout.setChecked(False)
    dlg._on_save()

    assert "_sheet_layout" not in dlg.result_data["selected_attributes"]


def test_create_template_dialog_layout_pruning_removes_empty_rows(qtbot):
    """Test that pruning removes completely empty rows."""
    source_attributes = {"Strength": 10}
    source_layout = [
        ["Strength"],
        [
            {"type": "divider"}
        ],  # Suppose a divider is pruned if alone? Wait, dividers aren't keys.
    ]

    # Real test: simple rows
    source_layout = [["Strength"], ["Intelligence"], ["Dexterity"]]
    source_attributes = {"Strength": 10, "Intelligence": 12, "Dexterity": 14}

    dlg = CreateTemplateDialog(
        source_tags=[],
        source_attributes=source_attributes,
        source_layout=source_layout,
    )
    qtbot.addWidget(dlg)

    dlg.attr_checks["Intelligence"].setChecked(False)

    dlg._on_save()

    resulting_layout = dlg.result_data["selected_attributes"].get("_sheet_layout")
    assert resulting_layout == [
        ["Strength"],
        # row 2 should be completely removed
        ["Dexterity"],
    ]
