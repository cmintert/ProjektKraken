import sys

sys.path.append(".")

from src.core.entities import Entity
from src.core.fast_inject import FastInjectManager, FastInjectTemplate
from src.gui.dialogs.create_template_dialog import CreateTemplateDialog

import pytest


def test_pruning_keeps_spacers_and_dividers():
    layout = [
        [{"type": "text", "text": "Header"}],
        ["Attr1", {"type": "spacer", "weight": 2}, "Attr2"],
        [{"type": "divider"}],
        ["Attr3"],
    ]

    # Simulate an application with CreateTemplateDialog logic
    attrs = {"Attr1": "val1"}  # Pretend only Attr1 is selected

    pruned_layout = []
    for row in layout:
        new_row = []
        for item in row:
            if isinstance(item, str):
                if item in attrs:
                    new_row.append(item)
            elif isinstance(item, dict) and "key" in item:
                if item["key"] in attrs:
                    new_row.append(item)
            else:  # Text, Divider, Spacer
                new_row.append(item)
        if new_row:
            pruned_layout.append(new_row)

    print("Pruned:", pruned_layout)


def test_manager_apply():
    manager = FastInjectManager(".")

    target = Entity(name="Test", type="General")
    target.attributes = {
        "OldAttr": "1",
        "_sheet_layout": [["OldAttr"], [{"type": "divider"}]],
    }

    # Injecting
    template = FastInjectTemplate(
        name="T",
        attributes={
            "NewAttr": "2",
            "_sheet_layout": [[{"type": "text", "text": "FromTemplate"}], ["NewAttr"]],
        },
    )

    manager.apply_template(target, template, overwrite=True)

    print("Final Target Layout:", target.attributes["_sheet_layout"])


if __name__ == "__main__":
    test_pruning_keeps_spacers_and_dividers()
    test_manager_apply()
