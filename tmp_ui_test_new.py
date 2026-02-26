import sys

sys.path.append(".")

from PySide6.QtWidgets import QApplication
from src.gui.widgets.sheet_builder import SheetBuilderWidget


def run_test():
    app = QApplication([])
    widget = SheetBuilderWidget()

    # Fast Inject assigns this to a BRAND NEW entity:
    layout = [
        [{"text": "A test ", "type": "text"}],
        [{"type": "divider"}],
        ["location"],
        ["result"],
    ]
    attributes = {"location": "South Pacific", "result": "Liberation of Cthulhu"}

    widget.load_attributes(attributes, layout)

    result_layout = widget.get_layout()
    print("New Entity Exported Layout:", result_layout)


run_test()
