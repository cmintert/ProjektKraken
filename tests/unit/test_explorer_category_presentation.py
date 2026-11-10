"""Readable type cues survive narrow rows, selection and theme changes."""

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QListView, QStyleOptionViewItem

from src.core.category_palette import CATEGORY_ROLES, category_role
from src.core.entities import Entity
from src.core.theme_defaults import DEFAULT_THEMES
from src.core.theme_manager import ThemeManager
from src.core.visual_roles import contrast
from src.gui.delegates.explorer_delegate import ExplorerDelegate
from src.gui.models.explorer_model import ExplorerModel

pytestmark = pytest.mark.ci_fast
THEMES = json.loads(Path("themes.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("theme", [*THEMES.values(), *DEFAULT_THEMES.values()])
def test_category_palette_text_contrast_and_distinct_standard_types(theme):
    for role in CATEGORY_ROLES:
        for background in ("app_bg", "surface"):
            assert contrast(theme[role], theme[background]) >= 4.5
    types = ["Character", "Location", "Faction", "Item", "Concept", "Species"]
    assert len({category_role("entity", value) for value in types}) == len(types)


def test_category_role_is_case_insensitive_and_independent_of_visible_types():
    assert category_role("entity", " Character ") == category_role(
        "entity", "character"
    )
    assert category_role("entity", "Custom guild") == category_role(
        "entity", "Custom guild"
    )


def test_long_name_retains_type_and_full_accessible_text(qtbot):
    entity = Entity(name="A very long name " * 12, type="Character")
    model = ExplorerModel()
    model.set_items([("entity", entity)])
    view = QListView()
    qtbot.addWidget(view)
    view.setModel(model)
    delegate = ExplorerDelegate(view)
    view.setItemDelegate(delegate)
    view.resize(300, 150)
    view.show()
    option = QStyleOptionViewItem()
    view.initViewItemOption(option)
    # The headless runner may have no system font; measure its actual glyphs.
    width = max(280, option.fontMetrics.horizontalAdvance("(Character)") * 3)
    option.rect = QRect(0, 0, width, 30)
    delegate.initStyleOption(option, model.index(0, 0))
    assert option.text.endswith("(Character)")
    assert "…" in option.text
    assert entity.name in model.index(0, 0).data(Qt.ItemDataRole.AccessibleTextRole)
    assert "Character" in model.index(0, 0).data(Qt.ItemDataRole.ToolTipRole)
    assert model.index(0, 0).data(ExplorerModel.ItemObjectRole) is entity


def test_custom_types_recolor_without_changing_checks_or_names(qapp, monkeypatch):
    entity = Entity(name="Council", type="Custom guild")
    model = ExplorerModel()
    model.set_items([("entity", entity)])
    index = model.index(0, 0)
    model.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    original = index.data(Qt.ItemDataRole.DisplayRole)
    model.set_use_hashed_colors(True)
    for theme in THEMES.values():
        monkeypatch.setattr(ThemeManager, "get_theme", lambda self: theme)
        model._on_theme_changed(theme)
        color = index.data(Qt.ItemDataRole.ForegroundRole).color().name()
        assert color == theme[category_role("entity", entity.type)].lower()
        assert index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
        assert index.data(Qt.ItemDataRole.DisplayRole) == original
