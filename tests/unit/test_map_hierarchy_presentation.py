"""Real themed hierarchy surfaces retain complete actions at narrow widths."""

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox

from src.core.theme_manager import ThemeManager
from src.gui.dialogs.map_hierarchy_dialog import MapHierarchyDialog
from src.gui.dialogs.register_detail_map_dialog import RegisterDetailMapDialog
from src.gui.utils.action_label_metrics import action_label_geometry
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.map.footprint_controls import FootprintControls
from src.services.map_reparenting import preservation_options
from tests.integration.test_map_hierarchy_authoring import (
    authoring as _authoring,
)
from tests.integration.test_map_hierarchy_authoring import (
    registration,
)

pytestmark = pytest.mark.ci_fast
authoring = _authoring


@pytest.mark.parametrize(
    "theme", list(json.loads(Path("themes.json").read_text("utf-8")))
)
@pytest.mark.parametrize("width,font_size", [(360, 10), (360, 20), (640, 10)])
def test_hierarchy_and_comparison_controls(
    authoring, qtbot, qapp, request, theme, width, font_size
):
    if os.environ.get("KRT_HIERARCHY_RENDER_CHILD") != "1":
        result = subprocess.run(
            [sys.executable, "-m", "pytest", request.node.nodeid, "-q", "--tb=short"],
            env=dict(os.environ, KRT_HIERARCHY_RENDER_CHILD="1"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return
    font = Path("C:/Windows/Fonts/segoeui.ttf")
    if font.exists():
        assert QFontDatabase.addApplicationFont(str(font)) >= 0
    qapp.setFont(QFont("Segoe UI", font_size))
    widget, handler, commands, _, _ = authoring
    manager = ThemeManager()
    manager.set_theme(theme)
    stylesheet = manager.format_stylesheet(
        Path("src/resources/main.qss").read_text("utf-8")
    )
    stylesheet = stylesheet.replace("font-size: 10pt;", f"font-size: {font_size}pt;")
    widget.setStyleSheet(stylesheet)
    hierarchy = MapHierarchyDialog(widget.maps_data, "source")
    qtbot.addWidget(hierarchy)
    hierarchy.setStyleSheet(stylesheet)
    hierarchy.resize(width, 650)
    hierarchy.show()
    qtbot.wait(0)
    assert hierarchy.width() == width
    assert hierarchy.font().pointSize() == font_size
    for button in (*hierarchy._buttons.values(), hierarchy._close_button):
        assert button.isVisible()
        assert button.label_geometry().fits, button.text()
    assert not hierarchy._buttons["detach"].isEnabled()
    hierarchy._buttons["navigate"].setFocus()
    QTest.keyClick(hierarchy._buttons["navigate"], Qt.Key.Key_Return)
    assert hierarchy.intent == ("navigate", "source")
    assert not commands

    maps = [
        replace(
            m,
            attributes={
                **m.attributes,
                "parent_map_id": "source",
                "registration": registration(),
            },
        )
        if m.id == "parent"
        else m
        for m in widget.maps_data
    ]
    child = next(m for m in maps if m.id == "child")
    candidates = RegisterDetailMapDialog.filter_candidate_parents(maps, child.id)
    picker = RegisterDetailMapDialog(
        child,
        candidates,
        preservation_options=preservation_options(maps, child.id, candidates),
    )
    qtbot.addWidget(picker)
    picker.setStyleSheet(stylesheet)
    picker.resize(width, 700)
    picker.show()
    picker._parent_combo.setCurrentIndex(picker._parent_combo.findData("parent"))
    qtbot.wait(0)
    assert picker.width() == width
    assert picker._keep_position.isVisible()
    assert picker._keep_position.label_geometry().fits
    assert (
        picker._placement_explanation.height()
        >= picker._placement_explanation.heightForWidth(
            picker._placement_explanation.width()
        )
    )
    assert action_label_geometry(picker._apply_button).fits
    picker._keep_position.setFocus()
    QTest.keyClick(picker._keep_position, Qt.Key.Key_Space)
    assert not picker.preserves_position()
    qtbot.waitUntil(lambda: action_label_geometry(picker._apply_button).fits)
    QTest.keyClick(picker._keep_position, Qt.Key.Key_Space)
    picker._apply_button.setFocus()
    assert picker._apply_button.hasFocus()
    for button in picker.findChild(QDialogButtonBox).buttons():
        assert action_label_geometry(button).fits
        assert picker.rect().contains(
            QRect(button.mapTo(picker, QPoint()), button.size())
        )
    picker_evidence = os.environ.get("KRT_HIERARCHY_EVIDENCE_DIR")
    if picker_evidence:
        Path(picker_evidence).mkdir(parents=True, exist_ok=True)
        assert picker.grab().save(
            str(
                Path(picker_evidence) / f"{theme}-{width}-{font_size}-parent-picker.png"
            )
        )
    QTest.keyClick(picker._apply_button, Qt.Key.Key_Return)
    assert picker.selected_parent_id() == "parent"
    assert picker.preserves_position()
    assert picker.registration() is None

    handler.on_register_detail_map_requested("source", "parent", registration())
    controls = FootprintControls(widget.view)
    qtbot.addWidget(controls)
    controls.setStyleSheet(
        stylesheet + StyleHelper.get_mode_panel_style(controls.objectName())
    )
    controls.reset_for_edit(True)
    controls.resize(width, controls.sizeHint().height())
    controls.show()
    qtbot.waitUntil(
        lambda: controls.opacity_label.geometry().top()
        > controls.status.geometry().bottom()
    )
    assert controls.width() == width
    assert controls.status.height() >= controls.status.heightForWidth(
        controls.status.width()
    )
    assert controls.opacity_label.geometry().top() > controls.status.geometry().bottom()
    for button in (controls.reset, controls.zoom, controls.lock):
        assert button.isVisible()
        assert button.label_geometry().fits, button.text()
        assert controls.rect().contains(button.geometry())
    controls.lock.setChecked(True)
    widget.view.setFocus()
    QTest.keyClick(widget.view, Qt.Key.Key_Right)
    QTest.keyClick(widget.view, Qt.Key.Key_BracketRight)
    assert not controls.reset.isEnabled()
    evidence = os.environ.get("KRT_HIERARCHY_EVIDENCE_DIR")
    if evidence:
        output = Path(evidence)
        output.mkdir(parents=True, exist_ok=True)
        hierarchy.show()
        qtbot.wait(0)
        stem = f"{theme}-{width}-{font_size}"
        assert hierarchy.grab().save(str(output / f"{stem}-hierarchy.png"))
        assert controls.grab().save(str(output / f"{stem}-controls.png"))
        assert widget.grab().save(str(output / f"{stem}-composed.png"))
        (output / f"{stem}.json").write_text(
            json.dumps(
                {
                    "requested_width": width,
                    "actual_width": hierarchy.width(),
                    "font": hierarchy.font().toString(),
                    "dpr": hierarchy.devicePixelRatioF(),
                    "platform": qapp.platformName(),
                }
            ),
            encoding="utf-8",
        )
    widget.view.finish_footprint_edit()
    assert commands[0].registration["master_center_norm"] == {"x": 0.4, "y": 0.6}
    assert commands[0].registration["rotation_deg"] == 25
