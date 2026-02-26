from src.gui.widgets.sheet_builder import SheetBuilderWidget


def test_rapid_edit_and_reload_crash(qtbot):
    """Simulate rapid editing followed by a reload to check for crashes."""
    sheet = SheetBuilderWidget()
    qtbot.addWidget(sheet)
    sheet.show()

    attrs = {"Str": 10, "Dex": 12, "Con": 14}
    sheet.load_attributes(attrs)

    # Get the first widget
    pair = sheet._pairs["Str"]
    edit = pair.value_edit

    # Simulate rapid typing
    for i in range(10):
        qtbot.keyClicks(edit, str(i))
        # After a few characters, simulate a reload (like an autosave trigger)
        if i == 5:
            sheet.load_attributes(attrs)
            # Re-fetch the pair as the old one is deleteLater-ed
            pair = sheet._pairs["Str"]
            edit = pair.value_edit

    assert sheet.get_attributes()["Str"] == 106789


def test_multiple_reloads_stress(qtbot):
    """Stress test with many reloads."""
    sheet = SheetBuilderWidget()
    qtbot.addWidget(sheet)

    attrs = {"A": 1, "B": 2, "C": 3}
    for _ in range(50):
        sheet.load_attributes(attrs)
        # Check that we didn't leak too many connections or widgets
        # (Hard to check directly without reflection, but we check for crash)

    assert len(sheet._pairs) == 3


def test_theme_change_after_reload(qtbot):
    """Check if theme change after reload crashes due to orphaned connections."""
    from src.core.theme_manager import ThemeManager

    tm = ThemeManager()

    sheet = SheetBuilderWidget()
    qtbot.addWidget(sheet)

    attrs = {"A": 1, "B": 2}
    sheet.load_attributes(attrs)

    # Reload to orphan previous widgets/handles
    sheet.load_attributes(attrs)

    # Change theme
    tm.theme_changed.emit(tm.get_theme())

    # If it didn't crash, we're good (for now)
    assert True
