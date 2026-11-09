import json
from math import isclose

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from rc_track_designer.canvas import TrackCanvas
from rc_track_designer.model import ConnectorRef, Point, TrackElement, TrackProject
from rc_track_designer.storage import FORMAT_VERSION, load_project, save_project
from rc_track_designer.ui import MainWindow


def boundary(kind="straight", **values):
    defaults = dict(start=Point(4, 4), width=0.10, length=3.0,
                    radius=2.0, angle_deg=45, element_type="boundary")
    defaults.update(values)
    return TrackElement(kind, **defaults)


@pytest.mark.parametrize("centimetres", [5, 10, 15, 20, 25])
def test_boundary_widths_are_stored_in_metres(centimetres):
    element = boundary(width=centimetres / 100)
    assert isclose(element.width, centimetres / 100)
    restored = TrackElement.from_dict(element.to_dict())
    assert restored.element_type == "boundary"
    assert isclose(restored.width, centimetres / 100)


def test_boundary_curve_uses_centerline_radius_and_rejects_invalid_inner_radius():
    curve = boundary("left", width=0.20, radius=1.25, angle_deg=90)
    assert isclose(curve.minimum_centerline_radius, 0.10)
    assert curve.has_valid_road_geometry
    assert isclose(curve.end_pose.point.x, 5.25)
    assert isclose(curve.end_pose.point.y, 5.25)
    invalid = boundary("right", width=0.25, radius=0.10)
    assert not invalid.has_valid_road_geometry


def test_boundaries_cannot_connect_to_normal_track_elements():
    road = TrackElement("straight", Point(1, 1), length=2)
    barrier = boundary(start=road.end_pose.point, heading_deg=road.end_pose.heading_deg)
    project = TrackProject(elements=[road, barrier])
    with pytest.raises(ValueError, match="same category"):
        project.connect(ConnectorRef(road.id, "end"), ConnectorRef(barrier.id, "start"))


def test_boundary_snapping_and_undo_redo_mode_change():
    app = QApplication.instance() or QApplication([])
    first = boundary(start=Point(2, 2), length=3)
    second = boundary(start=Point(5.15, 2), length=2)
    canvas = TrackCanvas()
    canvas.set_project(TrackProject(20, 12, [first, second], editor_mode="indoor"))
    canvas.scale = 40
    assert canvas._snap_element(second)
    assert canvas.project.connection_for(ConnectorRef(second.id, "start")) is not None

    canvas.set_editor_mode("normal")
    assert canvas.project.editor_mode == "normal"
    canvas.undo_stack.undo()
    assert canvas.project.editor_mode == "indoor"
    canvas.undo_stack.redo()
    assert canvas.project.editor_mode == "normal"
    selected = canvas.project.element_by_id(second.id)
    canvas.selected = selected
    canvas.selected_ids = {selected.id}
    original_heading = selected.heading_deg
    canvas.rotate_selected(5)
    assert canvas.selected.heading_deg == (original_heading + 5) % 360
    canvas.undo_stack.undo()
    assert canvas.selected.heading_deg == original_heading
    app.processEvents()


def test_boundaries_form_free_corners_but_snap_exactly_when_nearly_tangent():
    app = QApplication.instance() or QApplication([])
    anchor = boundary(start=Point(2, 2), length=3, heading_deg=0)
    corner = boundary(start=Point(5.2, 2.1), length=2, heading_deg=90)
    canvas = TrackCanvas()
    canvas.set_project(TrackProject(20, 12, [anchor, corner], editor_mode="indoor"))
    canvas.scale = 40

    assert canvas._snap_element(corner)
    assert corner.start == anchor.end_pose.point
    assert corner.heading_deg == 90
    assert canvas.project.connection_for(ConnectorRef(corner.id, "start")) is not None

    tangent_anchor = boundary(start=Point(10, 2), length=3, heading_deg=0)
    nearly_tangent = boundary(start=Point(13.2, 2.1), length=2, heading_deg=5)
    canvas.set_project(TrackProject(
        20, 12, [tangent_anchor, nearly_tangent], editor_mode="indoor"
    ))
    canvas.scale = 40
    assert canvas._snap_element(nearly_tangent)
    assert nearly_tangent.start == tangent_anchor.end_pose.point
    assert nearly_tangent.heading_deg == 0

    outside_angle_tolerance = boundary(start=Point(13.2, 2.1), length=2, heading_deg=10)
    canvas.set_project(TrackProject(
        20, 12, [tangent_anchor, outside_angle_tolerance], editor_mode="indoor"
    ))
    canvas.scale = 40
    assert canvas._snap_element(outside_angle_tolerance)
    assert outside_angle_tolerance.heading_deg == 10

    distant_anchor = boundary(start=Point(2, 8), length=3)
    outside_indoor_magnet = boundary(start=Point(5.6, 8), length=2)
    canvas.set_project(TrackProject(
        20, 12, [distant_anchor, outside_indoor_magnet], editor_mode="indoor"
    ))
    canvas.scale = 40
    assert not canvas._snap_element(outside_indoor_magnet)
    canvas.close()


def test_free_boundary_straight_resizes_from_either_connector_and_rotates_with_arrows():
    app = QApplication.instance() or QApplication([])
    element = boundary(start=Point(3, 6), length=3)
    canvas = TrackCanvas()
    canvas.resize(800, 600)
    canvas.set_project(TrackProject(20, 12, [element], editor_mode="indoor"))
    canvas.show(); app.processEvents()

    end = canvas.world_to_screen(element.end_pose.point).toPoint()
    destination = canvas.world_to_screen(Point(9.2, 6)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=end)
    QTest.mouseMove(canvas, destination)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=destination)

    assert canvas.selected.start == Point(3, 6)
    assert canvas.selected.length == pytest.approx(6.2, abs=0.03)
    canvas.undo_stack.undo()
    assert canvas.selected.length == 3.0

    QTest.keyClick(canvas, Qt.Key.Key_Left)
    assert canvas.selected.heading_deg == 5
    QTest.keyPress(canvas, Qt.Key.Key_Right)
    QTest.keyPress(canvas, Qt.Key.Key_Right)
    QTest.keyRelease(canvas, Qt.Key.Key_Right)
    assert canvas.selected.heading_deg == 355
    canvas.close()


def test_connected_boundary_straight_rotates_around_attached_curve_endpoint():
    app = QApplication.instance() or QApplication([])
    curve = boundary("left", start=Point(4, 4), radius=2, angle_deg=45)
    straight = boundary(
        start=curve.end_pose.point,
        heading_deg=curve.end_pose.heading_deg,
        length=4,
    )
    project = TrackProject(20, 15, [curve, straight], editor_mode="indoor")
    project.connect(ConnectorRef(curve.id, "end"), ConnectorRef(straight.id, "start"))
    canvas = TrackCanvas()
    canvas.resize(900, 650)
    canvas.set_project(project)
    canvas.show(); app.processEvents()
    pivot = straight.start
    original_length = straight.length
    free = canvas.world_to_screen(straight.end_pose.point).toPoint()
    destination = canvas.world_to_screen(Point(pivot.x, pivot.y + original_length)).toPoint()

    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=free)
    QTest.mouseMove(canvas, destination)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=destination)

    assert canvas.selected.start == pivot
    assert canvas.selected.length == pytest.approx(original_length, abs=0.03)
    assert canvas.selected.heading_deg == pytest.approx(90, abs=0.5)
    assert project.connection_for(ConnectorRef(straight.id, "start")) is not None
    canvas.undo_stack.undo()
    assert canvas.selected.heading_deg == pytest.approx(curve.end_pose.heading_deg)
    canvas.close()


def test_connected_boundary_lever_changes_length_continuously_and_snaps_to_target():
    app = QApplication.instance() or QApplication([])
    anchor = boundary(start=Point(3, 3), length=2)
    lever = boundary(start=anchor.end_pose.point, length=3)
    target = boundary(start=Point(10.37, 7.18), length=2, heading_deg=90)
    project = TrackProject(20, 15, [anchor, lever, target], editor_mode="indoor")
    project.connect(ConnectorRef(anchor.id, "end"), ConnectorRef(lever.id, "start"))
    canvas = TrackCanvas()
    canvas.resize(900, 650)
    canvas.set_project(project)
    canvas.show(); app.processEvents()
    pivot = lever.start
    free = canvas.world_to_screen(lever.end_pose.point).toPoint()
    destination = canvas.world_to_screen(target.start).toPoint()

    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=free)
    QTest.mouseMove(canvas, destination)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=destination)

    expected_length = ((target.start.x - pivot.x) ** 2
                       + (target.start.y - pivot.y) ** 2) ** 0.5
    assert canvas.selected.length == pytest.approx(expected_length)
    assert canvas.selected.end_pose.point == target.start
    assert project.connection_for(ConnectorRef(lever.id, "end")) is not None
    assert project.connection_for(ConnectorRef(lever.id, "start")) is not None
    canvas.undo_stack.undo()
    assert canvas.selected.length == 3
    assert len(canvas.project.connections) == 1
    canvas.close()


def test_indoor_rendering_uses_fixed_carpet_grid_and_boundary_colors():
    app = QApplication.instance() or QApplication([])
    element = boundary(start=Point(2, 2), length=4, width=0.20)
    canvas = TrackCanvas()
    canvas.resize(640, 400)
    canvas.set_project(TrackProject(12, 8, [element], editor_mode="indoor"))
    canvas.set_appearance({"hall": "#ffffff", "grid": "#000000", "track": "#ff00ff"})
    canvas.show(); app.processEvents()
    image = QImage(canvas.size(), QImage.Format.Format_ARGB32)
    image.fill(QColor("#000000"))
    painter = QPainter(image); canvas.render(painter, QPoint()); painter.end()
    midpoint = canvas.world_to_screen(element.centerline_midpoint).toPoint()
    assert image.pixelColor(midpoint) == QColor("#F4CC2E")
    carpet = canvas.world_to_screen(Point(8.4, 5.3)).toPoint()
    assert image.pixelColor(carpet).name().lower() == "#34383e"
    canvas.close()


def test_format_four_roundtrip_preserves_mode_categories_connections_and_units(tmp_path):
    first = boundary(start=Point(2, 2), length=2, width=0.15)
    second = boundary(start=first.end_pose.point, length=3, width=0.15)
    project = TrackProject(20, 12, [first, second], editor_mode="indoor")
    project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    path = tmp_path / "indoor.rct.json"
    save_project(project, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["format_version"] == FORMAT_VERSION == 4
    loaded = load_project(path)
    assert loaded.editor_mode == "indoor"
    assert [item.element_type for item in loaded.elements] == ["boundary", "boundary"]
    assert isclose(loaded.elements[0].width, 0.15)
    assert len(loaded.connections) == 1


def test_straight_boundary_magnet_point_pose_and_json_roundtrip(tmp_path):
    element = boundary(start=Point(2, 3), length=8, heading_deg=90,
                       magnet_points={"middle": 0.25})
    pose = element.pose_at("magnet:middle")
    assert pose.point.x == pytest.approx(2)
    assert pose.point.y == pytest.approx(5)
    assert pose.heading_deg == pytest.approx(90)

    path = tmp_path / "magnet-points.rct.json"
    save_project(TrackProject(20, 12, [element], editor_mode="indoor"), path)
    restored = load_project(path).elements[0]
    assert restored.magnet_points == {"middle": 0.25}
    assert restored.pose_at("magnet:middle") == pose


def test_add_and_remove_magnet_point_are_undoable_and_free_peer():
    app = QApplication.instance() or QApplication([])
    anchor = boundary(start=Point(2, 2), length=6)
    peer = boundary(start=Point(5, 2), heading_deg=90)
    canvas = TrackCanvas()
    canvas.set_project(TrackProject(20, 12, [anchor, peer], editor_mode="indoor"))

    connector = canvas.add_magnet_point(anchor, 0.5)
    point_id = connector.endpoint.split(":", 1)[1]
    assert anchor.magnet_points[point_id] == pytest.approx(0.5)
    canvas.project.connect(connector, ConnectorRef(peer.id, "start"))
    assert canvas.remove_magnet_point(connector)
    assert point_id not in anchor.magnet_points
    assert canvas.project.connection_for(ConnectorRef(peer.id, "start")) is None

    canvas.undo_stack.undo()
    restored = canvas.project.element_by_id(anchor.id)
    assert restored.magnet_points[point_id] == pytest.approx(0.5)
    assert canvas.project.connection_for(connector) is not None
    canvas.undo_stack.redo()
    assert point_id not in canvas.project.element_by_id(anchor.id).magnet_points
    app.processEvents()


def test_magnet_point_context_candidate_is_indoor_straight_only():
    app = QApplication.instance() or QApplication([])
    element = boundary(start=Point(2, 2), length=6)
    canvas = TrackCanvas()
    canvas.resize(800, 500)
    canvas.set_project(TrackProject(20, 12, [element], editor_mode="indoor"))
    middle = canvas.world_to_screen(Point(5, 2))
    candidate = canvas._magnet_insertion_at(middle, element)
    assert candidate is not None
    assert candidate[1] == pytest.approx(0.5)

    canvas.project.editor_mode = "normal"
    assert canvas._magnet_insertion_at(middle, element) is None
    road = TrackElement("straight", Point(2, 3), length=6)
    canvas.project.editor_mode = "indoor"
    assert canvas._magnet_insertion_at(canvas.world_to_screen(Point(5, 3)), road) is None
    app.processEvents()


def test_boundary_endpoint_snaps_to_added_magnet_point():
    app = QApplication.instance() or QApplication([])
    anchor = boundary(start=Point(2, 2), length=6,
                      magnet_points={"centre": 0.5})
    moving = boundary(start=Point(5.12, 2.08), length=2, heading_deg=90)
    canvas = TrackCanvas()
    canvas.scale = 40
    canvas.set_project(TrackProject(20, 12, [anchor, moving], editor_mode="indoor"))

    assert canvas._snap_element(moving)
    target = ConnectorRef(anchor.id, "magnet:centre")
    connection = canvas.project.connection_for(target)
    assert connection is not None
    assert moving.start == anchor.pose_at("magnet:centre").point
    assert canvas.project.is_free(target) is False
    app.processEvents()


def test_dragging_connected_magnet_point_moves_attached_boundary_and_is_undoable():
    app = QApplication.instance() or QApplication([])
    anchor = boundary(start=Point(2, 2), length=8,
                      magnet_points={"custom": 0.25})
    attached = boundary(start=Point(4, 2), length=2, heading_deg=90)
    project = TrackProject(20, 12, [anchor, attached], editor_mode="indoor")
    magnet = ConnectorRef(anchor.id, "magnet:custom")
    project.connect(magnet, ConnectorRef(attached.id, "start"))
    canvas = TrackCanvas()
    canvas.resize(900, 650)
    canvas.set_project(project)
    canvas.show(); app.processEvents()

    start = canvas.world_to_screen(Point(4, 2)).toPoint()
    destination = canvas.world_to_screen(Point(6, 2)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, destination)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=destination)

    moved_anchor = canvas.project.element_by_id(anchor.id)
    moved_attached = canvas.project.element_by_id(attached.id)
    assert moved_anchor.magnet_points["custom"] == pytest.approx(0.5, abs=0.002)
    assert moved_attached.start.x == pytest.approx(6, abs=0.02)
    assert moved_attached.start.y == pytest.approx(2, abs=0.02)
    assert canvas.project.connector_alignment_error(
        magnet, ConnectorRef(attached.id, "start"))[0] == pytest.approx(0)
    canvas.undo_stack.undo()
    assert canvas.project.element_by_id(anchor.id).magnet_points["custom"] == pytest.approx(0.25)
    assert canvas.project.element_by_id(attached.id).start == Point(4, 2)
    canvas.undo_stack.redo()
    assert canvas.project.element_by_id(attached.id).start.x == pytest.approx(6, abs=0.02)
    canvas.close()


def test_dragging_magnet_moves_only_direct_element_and_releases_its_next_link():
    app = QApplication.instance() or QApplication([])
    anchor = boundary(start=Point(2, 2), length=8,
                      magnet_points={"custom": 0.25})
    direct = boundary(start=Point(4, 2), length=2)
    remainder = boundary(start=Point(6, 2), length=2)
    magnet = ConnectorRef(anchor.id, "magnet:custom")
    next_link = ConnectorRef(direct.id, "end")
    project = TrackProject(20, 12, [anchor, direct, remainder], editor_mode="indoor")
    project.connect(magnet, ConnectorRef(direct.id, "start"))
    project.connect(next_link, ConnectorRef(remainder.id, "start"))
    canvas = TrackCanvas()
    canvas.resize(900, 650)
    canvas.set_project(project)
    canvas.show(); app.processEvents()

    start = canvas.world_to_screen(Point(4, 2)).toPoint()
    destination = canvas.world_to_screen(Point(5, 2)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, destination)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=destination)

    assert canvas.project.element_by_id(direct.id).start.x == pytest.approx(5, abs=0.02)
    assert canvas.project.element_by_id(remainder.id).start == Point(6, 2)
    assert canvas.project.connection_for(magnet) is not None
    assert canvas.project.connection_for(next_link) is None
    canvas.undo_stack.undo()
    assert canvas.project.element_by_id(direct.id).start == Point(4, 2)
    assert canvas.project.element_by_id(remainder.id).start == Point(6, 2)
    assert canvas.project.connection_for(next_link) is not None
    canvas.close()


@pytest.mark.parametrize("version", [1, 2, 3])
def test_legacy_projects_remain_normal_tracks(tmp_path, version):
    element = TrackElement("straight", Point(1, 1)).to_dict()
    element.pop("element_type")
    data = {
        "format": "rc-track-designer", "format_version": version,
        "hall": {"length": 20, "width": 10}, "elements": [element],
    }
    if version >= 2:
        data["connections"] = []
    path = tmp_path / f"v{version}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    project = load_project(path)
    assert project.editor_mode == "normal"
    assert project.elements[0].element_type == "track"


def test_mode_switch_starts_empty_area_and_updates_indoor_controls():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    app.processEvents()
    normal_properties_width = window.properties_dock.width()
    road = TrackElement("straight", Point(3, 3))
    window.canvas.set_project(TrackProject(30, 18, elements=[road]))
    window.mode_combo.setCurrentIndex(window.mode_combo.findData("indoor"))
    app.processEvents()
    assert window.canvas.project.editor_mode == "indoor"
    assert window.canvas.project.elements == []
    assert window.canvas.project.hall_length == 30
    assert window.canvas.project.hall_width == 18
    assert window.current_path is None
    assert window.width_spin.suffix() == " cm"
    assert window.width_spin.value() == 10
    assert window.property_spins["width"].suffix() == " cm"
    assert window.property_spins["width"].value() == 10
    assert window.palette_mode_label.text() == window.tr_text("Indoor mode")
    assert window.straight_action.text() == window.tr_text("Straight")
    assert window.curve_label.text().strip() == window.tr_text("Curves:")
    assert all(button.isVisible() for button in window.curve_buttons)
    assert window.properties_dock.width() == normal_properties_width
    window.dirty = False
    window.close()


def test_mode_switch_cancel_keeps_unsaved_project(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    road = TrackElement("straight", Point(3, 3))
    window.canvas.set_project(TrackProject(25, 12, [road]))
    window.dirty = True
    monkeypatch.setattr(
        QMessageBox, "exec",
        lambda self: QMessageBox.StandardButton.Cancel.value,
    )

    window.mode_combo.setCurrentIndex(window.mode_combo.findData("indoor"))
    assert window.canvas.project.editor_mode == "normal"
    assert window.mode_combo.currentData() == "normal"
    assert window.canvas.project.elements[0].id == road.id
    window.dirty = False
    window.close()
    app.processEvents()


def test_mode_switch_saves_dirty_project_before_opening_empty_mode(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    road = TrackElement("straight", Point(3, 3))
    window.canvas.set_project(TrackProject(25, 12, [road]))
    window.dirty = True
    saved = []
    monkeypatch.setattr(
        QMessageBox, "exec",
        lambda self: QMessageBox.StandardButton.Save.value,
    )
    monkeypatch.setattr(window, "save", lambda: saved.append(True) or True)

    window.mode_combo.setCurrentIndex(window.mode_combo.findData("indoor"))
    assert saved == [True]
    assert window.canvas.project.editor_mode == "indoor"
    assert window.canvas.project.elements == []
    assert window.canvas.project.hall_length == 25
    assert window.canvas.project.hall_width == 12
    assert window.dirty is False
    window.close()
    app.processEvents()
