"""Assisted real-widget replay of modified journey and geometry drafts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

os.environ["QT_QPA_PLATFORM"] = "offscreen"
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QObject, QPointF, QSettings, Qt, Signal  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase, QImage  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QVBoxLayout,
    QWidget,
)

from src.app.coordinators.feature_geometry_coordinator import (  # noqa: E402
    FeatureGeometryCoordinator,
)
from src.app.coordinators.map_edit_transition_coordinator import (  # noqa: E402
    MapEditTransitionCoordinator,
)
from src.app.coordinators.trajectory_edit_coordinator import (  # noqa: E402
    TrajectoryEditCoordinator,
)
from src.commands.base_command import CommandResult  # noqa: E402
from src.core.map import Map  # noqa: E402
from src.core.theme_manager import ThemeManager  # noqa: E402
from src.gui.widgets.map_widget import MapWidget  # noqa: E402

OUTPUT = Path(__file__).parent
MODIFIED_X = 0.35


class Signals(QObject):
    """No database: snapshots and acknowledgements are explicit test inputs."""

    command_finished = Signal(CommandResult)
    error_occurred = Signal(str)
    markers_ready = Signal(str, list)
    feature_geometry_states_ready = Signal(str, list)
    playhead_time_changed = Signal(float)

    def get_playhead_time(self) -> float:
        """Keep the viewing date fixed across declined navigation."""
        return 5.0


class Window(QWidget):
    """Minimal application composition for deterministic map replay."""

    command_requested = Signal(object)

    def __init__(self) -> None:
        """Compose production widgets/coordinators with synthetic snapshots."""
        super().__init__()
        self.current_world = SimpleNamespace(id="replay-world")
        self.worker = Signals(self)
        self.timeline = Signals(self)
        self.data_handler = Signals(self)
        self.map_widget = MapWidget(self)
        self.map_widget.view.setViewport(QWidget())
        self.map_handler = SimpleNamespace(
            on_trajectories_ready=lambda _map, rows: self.map_widget.set_trajectories(
                rows
            )
        )
        self.messages: list[str] = []
        self.status_bar = SimpleNamespace(
            showMessage=lambda text, *_: self.messages.append(text)
        )
        self.statusBar = lambda: self.status_bar
        self.trajectory = TrajectoryEditCoordinator(self)
        self.geometry = FeatureGeometryCoordinator(self)
        self.decision = "keep"
        self.guard = MapEditTransitionCoordinator(
            [self.trajectory, self.geometry],
            lambda: self.current_world.id,
            lambda *_: self.decision,
            self.messages.append,
            self,
        )
        self.app_coordinator = SimpleNamespace(map_edits=self.guard)
        self.trajectory.bind_ui()
        self.geometry.bind_ui()
        self.map_widget.edit_transition_handler = self.guard.request_transition
        layout = QVBoxLayout(self)
        layout.addWidget(self.map_widget)
        self.resize(1000, 760)


def main() -> None:
    """Verify Keep editing retains modified drafts, then explicit Discard leaves."""
    with TemporaryDirectory(prefix="kraken-krt26-replay-") as temporary:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, temporary
        )
        app = QApplication([])
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeuib.ttf")
        app.setFont(QFont("Segoe UI", 9))
        manager = ThemeManager(str(REPO / "themes.json"))
        manager.load_stylesheet(str(REPO / "src/resources/main.qss"))
        manager.set_theme("dark_mode", app)
        window = Window()
        window.setObjectName("MapReplayWindow")
        window.setStyleSheet(
            "QWidget#MapReplayWindow { background: "
            + manager.get_theme()["app_bg"] + "; }"
        )
        widget = window.map_widget
        widget.set_maps(
            [
                Map(id="first", name="Upper Rhine", image_path="fixture"),
                Map(id="second", name="Other map", image_path="fixture"),
            ]
        )
        widget.select_map("first")
        image = QImage(800, 500, QImage.Format.Format_RGB32)
        image.fill(manager.get_theme()["surface"])
        image_path = Path(temporary) / "map.png"
        assert image.save(str(image_path))
        assert widget.load_map(str(image_path))
        item = widget.view.pixmap_item
        assert item is not None
        widget.on_time_changed(5.0)
        widget.add_marker("person", "entity", "Tasgillia", 0.2, 0.2)
        window.show()
        app.processEvents()
        widget.view.setSceneRect(item.boundingRect())
        widget.view.fitInView(item, Qt.AspectRatioMode.KeepAspectRatio)
        commands: list[object] = []
        window.command_requested.connect(commands.append)
        window.trajectory.on_trajectories_ready(
            "first",
            [
                {
                    "marker_id": "person",
                    "trajectory_id": "journey",
                    "keyframes": [
                        {"t": 0.0, "x": 0.2, "y": 0.2, "point_kind": "timed"},
                        {"t": 10.0, "x": 0.8, "y": 0.8, "point_kind": "timed"},
                    ],
                    "row_snapshot": {"id": "journey", "trajectory": "fixture"},
                }
            ],
        )
        window.trajectory.start_edit("person")
        session = window.trajectory._session
        assert session is not None
        window.trajectory.move_keyframe(
            session.working_keyframes[0].edit_id, MODIFIED_X, 0.4
        )
        widget.select_map("second")
        assert widget.get_selected_map_id() == "first"
        assert session.working_keyframes[0].x == MODIFIED_X and commands == []
        widget.set_maps(widget.maps_data)
        assert window.trajectory._session is session
        app.processEvents()
        assert window.grab().save(str(OUTPUT / "journey-kept.png"))
        window.decision = "discard"
        widget.select_map("second")
        assert widget.get_selected_map_id() == "second"
        assert not window.trajectory.is_active and commands == []
        widget.select_map("first")
        geometry = [{"x": 0.1, "y": 0.1}, {"x": 0.6, "y": 0.6}]
        widget.add_marker(
            "border",
            "entity",
            "Upper Rhine border",
            0.35,
            0.35,
            feature_type="path",
            geometry=geometry,
        )
        snapshot = {
            "id": "marker",
            "map_id": "first",
            "object_id": "border",
            "object_type": "entity",
            "label": "Upper Rhine border",
            "x": 0.35,
            "y": 0.35,
            "feature_type": "path",
            "geometry": geometry,
            "attributes": {},
            "style": {},
        }
        window.geometry.on_markers_ready("first", [snapshot])
        window.geometry._start_session(
            "first",
            "marker",
            snapshot,
            "base",
            {
                "geometry": geometry,
                "anchor_x": 0.35,
                "anchor_y": 0.35,
            },
            [],
        )
        widget.view._vertex_editor._on_vertex_moved(0, QPointF(240, 180))
        draft = window.geometry._session["working_geometry"]
        assert draft != geometry
        window.decision = "keep"
        widget.select_map("second")
        assert widget.get_selected_map_id() == "first"
        assert window.geometry._session["working_geometry"] == draft
        widget.set_maps(widget.maps_data)
        assert widget.view.is_editing_vertices and commands == []
        app.processEvents()
        assert window.grab().save(str(OUTPUT / "geometry-kept.png"))
        window.decision = "apply"
        widget.select_map("second")
        assert len(commands) == 1 and window.guard.is_waiting
        command = commands[0]
        window.geometry.on_command_finished(CommandResult(
            False, "Injected save failure", command_name=type(command).__name__,
            data={"command_id": command.command_id},
        ))
        assert widget.get_selected_map_id() == "first"
        assert not window.guard.is_waiting and widget.view.is_editing_vertices
        assert window.geometry._session["working_geometry"] == draft
        app.processEvents()
        assert window.grab().save(str(OUTPUT / "geometry-after-failed-apply.png"))
        window.geometry.on_markers_ready("first", [{**snapshot, "x": 0.4}])
        assert not widget.is_active_map_session_valid()
        assert widget.btn_geometry_discard_reload.isVisible()
        window.resize(420, 760)
        app.processEvents()
        assert window.grab().save(str(OUTPUT / "geometry-conflict-narrow.png"))
        window.decision = "discard"
        widget.select_map("second")
        assert not window.geometry.is_active and len(commands) == 1
        (OUTPUT / "replay.json").write_text(
            json.dumps(
                {
                    "evidence": "Assisted production-widget replay; no human timing claim",
                    "journey_modified_keep_refresh_discard": "passed",
                    "geometry_vertex_modified_keep_refresh_discard": "passed",
            "geometry_failed_apply_restores_handles_and_cancels_navigation": "passed",
                    "commands_before_apply": 0,
                    "viewing_date": 5.0,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        window.hide()


if __name__ == "__main__":
    main()
