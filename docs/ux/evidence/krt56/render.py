"""Disposable render probe; output is retained under docs/ux/evidence/krt56."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root))
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QMainWindow

QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp())
app = QApplication([])
for name in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf"):
    QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts") / name))
app.setOrganizationName("KrakenRenderProbe")
app.setApplicationName("KRT56")
from src.core.entities import Entity
from src.core.events import Event
from src.core.theme_manager import ThemeManager
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.longform.editor import LongformEditorWidget

theme = ThemeManager(str(root / "themes.json"))
theme.apply_theme(app, (root / "src/resources/main.qss").read_text(encoding="utf-8"))
output = root / "docs/ux/evidence/krt56"
output.mkdir(parents=True, exist_ok=True)
records = []
for kind, cls, owner in [
    ("entity", EntityEditorWidget, Entity(id="target", name="Tasgilla", type="Character")),
    ("event", EventEditorWidget, Event(id="target", name="Winter Council", lore_date=100)),
]:
    parent = QMainWindow()
    widget = cls(parent)
    parent.setCentralWidget(widget)
    widget.gallery.set_owner = Mock()
    getattr(widget, "load_" + kind)(owner)
    widget._suggestion_items = [("source", "House Bjonaer", "entity")]
    panel = widget.relation_authoring
    panel.stage_drop({"id": "source", "type": "entity"})
    widget.inspector.activate_section_id("connections")
    parent.resize(560, 800)
    parent.show()
    for name in theme.themes:
        theme.set_theme(name, app)
        parent.resize(560, 800)
        panel.apply_button.setFocus()
        app.processEvents()
        filename = f"{kind}-{name}.png"
        widget.tab_relations.grab().save(str(output / filename))
        records.append({"file": filename, "width": panel.width(),
                        "height": panel.height(), "connect_enabled": panel.apply_button.isEnabled()})
    parent.resize(360, 800)
    app.processEvents()
    widget.tab_relations.grab().save(str(output / f"{kind}-narrow.png"))
    panel.apply_button.setEnabled(False)
    app.processEvents()
    widget.tab_relations.grab().save(str(output / f"{kind}-disabled.png"))
    parent.close()
    parent.deleteLater()
    app.processEvents()
view = LongformEditorWidget()
view.load_sequence([{"id": "target", "name": "Tasgilla", "table": "entities",
                     "heading_level": 1, "content": "Description", "meta": {}}])
view.resize(590, 480)
view.show()
app.processEvents()
view.grab().save(str(output / "longform-no-selection.png"))
view.outline.setCurrentItem(view.outline.topLevelItem(0))
view.btn_open_inspector.setFocus()
app.processEvents()
view.grab().save(str(output / "longform-narrow-selected.png"))
view.close()
(output / "render.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
print(f"Rendered {len(records)} themed inspector drafts plus narrow/disabled/Longform states")
