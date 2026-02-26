import sys

sys.path.append(".")

from PySide6.QtWidgets import QApplication
from src.gui.widgets.sheet_builder import SheetBuilderWidget


def run_test():
    app = QApplication([])
    widget = SheetBuilderWidget()

    # Load initial Layout with Text, Divider, Spacer
    layout = [
        [{"type": "text", "text": "Hello World"}],
        [{"type": "divider"}],
        ["Attr1", {"type": "spacer", "weight": 2}, "Attr2"],
    ]
    attributes = {"Attr1": "val1", "Attr2": "val2"}

    widget.load_attributes(attributes, layout)

    # Now get the layout back
    result_layout = widget.get_layout()
    print("Exported Layout:", result_layout)

    # Now simulate apply template which gives a layout with text and divider
    new_attributes = {"Attr1": "val1", "Attr2": "val2", "Attr3": "val3"}
    new_layout = result_layout + [
        [{"type": "text", "text": "Appended text"}],
        [{"type": "divider"}],
        ["Attr3"],
    ]

    widget.load_attributes(new_attributes, new_layout)
    final_layout = widget.get_layout()
    print("Final Exported Layout:", final_layout)


run_test()
