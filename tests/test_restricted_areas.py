import os
from math import cos, hypot, radians, sin

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rc_track_designer.canvas import TrackCanvas
from rc_track_designer.i18n import TranslationManager
from rc_track_designer.model import (
    ConnectorRef, PlanningObject, Point, TrackElement, TrackProject,
)
from rc_track_designer.planning import drivers_stand_handles, planning_hit_test
from rc_track_designer.printing import PrintOptions, pdf_printer, render_project_to_printer
from rc_track_designer.restricted import (
    circle_handle, polygon_from_world, polygon_world_points, valid_polygon,
)
from rc_track_designer.storage import load_project, save_project
from rc_track_designer.ui import MainWindow


@pytest.fixture(scope="module", autouse=True)
def application():
    yield QApplication.instance() or QApplication([])


def _canvas():
    canvas = TrackCanvas()
    canvas.resize(900, 650)
    canvas.set_project(TrackProject(30, 20, editor_mode="indoor"))
    canvas.show()
    QApplication.processEvents()
    return canvas


@pytest.mark.parametrize("shape,kind,length,width", [
    ("rectangle", "restricted_rectangle", 4, 2),
    ("circle", "restricted_circle", 2, 2),
])
def test_place_restricted_area_and_undo(shape, kind, length, width):
    canvas = _canvas()
    canvas.set_restricted_placement(shape)
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton,
                     pos=canvas.world_to_screen(Point(10, 8)).toPoint())
    item = canvas.project.planning_objects[0]
    assert (item.kind, item.length, item.width) == (kind, length, width)
    canvas.undo_stack.undo()
    assert not canvas.project.planning_objects
    canvas.undo_stack.redo()
    assert canvas.project.planning_objects[0].kind == kind
    canvas.close()


@pytest.mark.parametrize("heading", [30, 45, 90])
def test_rotated_rectangle_resizes_with_opposite_side_fixed(heading):
    canvas = _canvas()
    item = PlanningObject("restricted_rectangle", Point(12, 9), 4, 2,
                          heading_deg=heading)
    canvas.project.planning_objects.append(item)
    canvas.selected_planning = item
    before = drivers_stand_handles(item)
    start = canvas.world_to_screen(before["right"]).toPoint()
    center = canvas.world_to_screen(item.center).toPoint()
    delta = start - center
    target = start + QPoint(round(delta.x() * .3), round(delta.y() * .3))
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, target)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)
    after = drivers_stand_handles(item)
    assert item.length > 4
    assert after["left"].x == pytest.approx(before["left"].x, abs=.03)
    assert after["left"].y == pytest.approx(before["left"].y, abs=.03)
    canvas.close()


def test_circle_numeric_and_graphic_diameter_stays_circular():
    canvas = _canvas()
    item = PlanningObject("restricted_circle", Point(10, 8), 2, 2)
    canvas.project.planning_objects.append(item)
    canvas.selected_planning = item
    canvas.change_selected("diameter", length=3.5)
    assert item.length == item.width == pytest.approx(3.5)
    start = canvas.world_to_screen(circle_handle(item)).toPoint()
    target = start + QPoint(30, 0)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, target)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)
    assert item.length == item.width
    assert item.length > 3.5
    canvas.undo_stack.undo()
    assert canvas.project.planning_objects[0].length == pytest.approx(3.5)
    canvas.close()


@pytest.mark.parametrize("points", [
    [Point(2, 2), Point(6, 2), Point(4, 5)],
    [Point(2, 2), Point(6, 2), Point(6, 5), Point(2, 5)],
    [Point(2, 2), Point(7, 2), Point(7, 6), Point(4, 4), Point(2, 6)],
])
def test_valid_triangles_quads_and_concave_polygons(points):
    assert valid_polygon(points)
    item = polygon_from_world(points)
    assert item.kind == "restricted_polygon"
    assert len(item.points) == len(points)


def test_self_intersecting_polygon_is_rejected():
    assert not valid_polygon([
        Point(2, 2), Point(6, 6), Point(2, 6), Point(6, 2),
    ])


def test_polygon_creation_close_escape_and_vertex_edits():
    canvas = _canvas()
    points = [Point(5, 5), Point(9, 5), Point(9, 8), Point(5, 8)]
    canvas.set_restricted_placement("polygon")
    for point in points:
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton,
                         pos=canvas.world_to_screen(point).toPoint())
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton,
                     pos=canvas.world_to_screen(points[0]).toPoint())
    item = canvas.project.planning_objects[0]
    assert item.kind == "restricted_polygon" and len(item.points) == 4

    before = polygon_world_points(item)[0]
    start = canvas.world_to_screen(before).toPoint()
    target = start + QPoint(15, -10)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, target)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)
    assert polygon_world_points(item)[0] != before
    canvas.undo_stack.undo()

    canvas.selected_planning = canvas.project.planning_objects[0]
    edge_point = Point(7, 5)
    canvas.insert_polygon_vertex(0, edge_point)
    assert len(canvas.selected_planning.points) == 5
    canvas.remove_polygon_vertex(1)
    assert len(canvas.selected_planning.points) == 4

    canvas.set_restricted_placement("polygon")
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton,
                     pos=canvas.world_to_screen(Point(12, 5)).toPoint())
    canvas.cancel_planning_placement()
    assert len(canvas.project.planning_objects) == 1
    canvas.close()


def test_restricted_roundtrip_lock_hit_test_and_pdf(tmp_path):
    polygon = polygon_from_world([Point(10, 4), Point(14, 4), Point(13, 7)])
    polygon.locked = True
    project = TrackProject(30, 20, editor_mode="indoor", planning_objects=[
        PlanningObject("restricted_rectangle", Point(5, 5), 4, 2, heading_deg=25),
        PlanningObject("restricted_circle", Point(20, 5), 3, 3),
        polygon,
    ])
    path = tmp_path / "restricted.rct.json"
    save_project(project, path)
    loaded = load_project(path)
    assert [item.kind for item in loaded.planning_objects] == [
        "restricted_rectangle", "restricted_circle", "restricted_polygon",
    ]
    assert loaded.planning_objects[2].locked
    assert len(loaded.planning_objects[2].points) == 3
    mapper = lambda point: QPoint(round(point.x * 20), round(point.y * 20))
    assert all(planning_hit_test(item, mapper(item.center), mapper)
               for item in loaded.planning_objects)
    pdf = tmp_path / "restricted.pdf"
    options = PrintOptions(show_grid=False, grayscale=True)
    render_project_to_printer(pdf_printer(pdf, options), loaded, options)
    assert pdf.read_bytes().startswith(b"%PDF") and pdf.stat().st_size > 1000


@pytest.mark.parametrize("item", [
    PlanningObject("restricted_rectangle", Point(8, 8), 4, 2),
    PlanningObject("restricted_circle", Point(8, 8), 2, 2),
    polygon_from_world([Point(6, 6), Point(10, 6), Point(8, 10)]),
])
def test_lock_unlock_delete_and_undo(item):
    canvas = _canvas()
    canvas.project.planning_objects.append(item)
    canvas.selected_planning = item
    canvas.toggle_selected_planning_lock()
    assert item.locked and canvas.selected_planning is item
    old_center = item.center
    canvas.change_selected("blocked", x=old_center.x + 2)
    assert item.center == old_center
    canvas.toggle_selected_planning_lock()
    assert not item.locked
    canvas.delete_selected()
    assert not canvas.project.planning_objects
    canvas.undo_stack.undo()
    assert canvas.project.planning_objects[0].kind == item.kind
    canvas.close()


def test_restricted_tools_are_indoor_only_and_translated():
    window = MainWindow()
    window.canvas.set_project(TrackProject(editor_mode="normal"))
    window._apply_mode_ui()
    assert not window.restricted_areas_button.isHidden()
    assert not window.restricted_areas_button.isEnabled()
    assert not window.restricted_rectangle_action.isEnabled()
    window.canvas.set_project(TrackProject(editor_mode="indoor"))
    window._apply_mode_ui()
    assert not window.restricted_areas_button.isHidden()
    assert window.restricted_areas_button.isEnabled()
    assert window.restricted_rectangle_action.isVisible()
    assert window.restricted_rectangle_action.isEnabled()
    assert window.restricted_rectangle_action.text() == "Rechteckige Sperrfläche"
    assert window.starting_grid_button.text() == "Startplätze"
    assert window.drivers_stand_button.text() == "Fahrerstand"
    assert window.start_finish_button.width() == window.starting_grid_button.width()
    assert window.starting_grid_button.width() == window.drivers_stand_button.width()
    assert TranslationManager("en").tr("Diameter:") == "Diameter:"
    window.dirty = False
    window.close()


def test_indoor_boundary_cannot_cross_restricted_area_but_may_touch_contour():
    canvas = _canvas()
    area = PlanningObject("restricted_rectangle", Point(10, 8), 4, 2)
    canvas.project.planning_objects.append(area)
    crossing = TrackElement("straight", Point(5, 8), heading_deg=0,
                            length=10, width=.1, element_type="boundary")
    touching = TrackElement("straight", Point(4, 8), heading_deg=0,
                            length=4, width=.1, element_type="boundary")
    assert canvas._boundary_crosses_restricted(crossing)
    assert not canvas._boundary_crosses_restricted(touching)
    assert canvas._restricted_contour_snap(Point(8.08, 8)) == Point(8, 8)
    canvas.close()


def test_restricted_contour_uses_small_dedicated_snap_radius():
    canvas = _canvas()
    area = PlanningObject("restricted_rectangle", Point(10, 8), 4, 2)
    canvas.project.planning_objects.append(area)
    near = Point(8 - 5 / canvas.scale, 8)
    far = Point(8 - 12 / canvas.scale, 8)
    assert canvas._restricted_contour_snap(near) == Point(8, 8)
    assert canvas._restricted_contour_snap(far) is None
    canvas.close()


def test_attached_boundary_can_be_pulled_clear_without_resnapping():
    canvas = _canvas()
    area = PlanningObject("restricted_rectangle", Point(10, 8), 4, 2)
    boundary = TrackElement("straight", Point(5, 8), heading_deg=0,
                            length=3, width=.1, element_type="boundary")
    canvas.project.planning_objects.append(area)
    canvas.project.elements.append(boundary)
    assert canvas._snap_boundary_to_restricted(boundary)
    assert canvas.project.restricted_attachments

    start = canvas.world_to_screen(Point(6.5, 8)).toPoint()
    target = start + QPoint(-20, 0)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, target)
    QApplication.processEvents()
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)

    assert not canvas.project.restricted_attachments
    assert boundary.end_pose.point.x < 8 - 12 / canvas.scale
    canvas.close()


def test_moved_boundary_snaps_endpoint_to_restricted_contour():
    canvas = _canvas()
    area = PlanningObject("restricted_circle", Point(12, 8), 4, 4)
    boundary = TrackElement("straight", Point(5, 8), heading_deg=0,
                            length=4.8, width=.1, element_type="boundary")
    canvas.project.planning_objects.append(area)
    canvas.project.elements.append(boundary)
    assert canvas._snap_boundary_to_restricted(boundary)
    assert boundary.end_pose.point.x == pytest.approx(10)
    assert boundary.end_pose.point.y == pytest.approx(8)
    assert not canvas._boundary_crosses_restricted(boundary)
    canvas.close()


def test_dragged_boundary_stops_at_restricted_contour_instead_of_rolling_back():
    canvas = _canvas()
    area = PlanningObject("restricted_rectangle", Point(10, 8), 4, 2)
    boundary = TrackElement("straight", Point(5, 8), heading_deg=0,
                            length=2, width=.1, element_type="boundary")
    canvas.project.planning_objects.append(area)
    canvas.project.elements.append(boundary)
    canvas.selected = boundary
    canvas.selected_ids = {boundary.id}
    moved_x, moved_y = canvas._move_selection_avoiding_restricted(3, 0)
    assert 0.99 < moved_x < 1.01
    assert moved_y == pytest.approx(0)
    assert boundary.end_pose.point.x == pytest.approx(8, abs=.01)
    assert not canvas._boundary_crosses_restricted(boundary)
    canvas.close()


def test_dragged_restricted_area_stops_at_boundary():
    canvas = _canvas()
    boundary = TrackElement("straight", Point(15, 3), heading_deg=90,
                            length=10, width=.1, element_type="boundary")
    area = PlanningObject("restricted_rectangle", Point(10, 8), 4, 2)
    canvas.project.elements.append(boundary)
    canvas.project.planning_objects.append(area)
    start = canvas.world_to_screen(area.center).toPoint()
    target = canvas.world_to_screen(Point(16, 8)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, target)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)
    assert area.center.x == pytest.approx(13, abs=.02)
    assert not canvas._restricted_area_crosses_boundaries(area)
    canvas.close()


def test_straight_magnet_point_can_snap_tangentially_to_restricted_contour():
    canvas = _canvas()
    area = PlanningObject("restricted_circle", Point(10, 8), 4, 4)
    boundary = TrackElement("straight", Point(7.8, 6), heading_deg=0,
                            length=4, width=.1, element_type="boundary",
                            magnet_points={"joint": .5})
    canvas.project.planning_objects.append(area)
    canvas.project.elements.append(boundary)
    assert canvas._snap_boundary_to_restricted(boundary)
    magnet = boundary.pose_at("magnet:joint").point
    assert ((magnet.x - area.center.x) ** 2
            + (magnet.y - area.center.y) ** 2) ** .5 == pytest.approx(2)
    assert not canvas._boundary_crosses_restricted(boundary)
    canvas.close()


def test_restricted_attachment_behaves_as_persistent_straight_joint(tmp_path):
    canvas = _canvas()
    area = PlanningObject("restricted_rectangle", Point(10, 8), 4, 2)
    boundary = TrackElement("straight", Point(5, 8), heading_deg=0,
                            length=3, width=.1, element_type="boundary")
    canvas.project.planning_objects.append(area)
    canvas.project.elements.append(boundary)
    assert canvas._snap_boundary_to_restricted(boundary)
    assert len(canvas.project.restricted_attachments) == 1
    attachment = canvas.project.restricted_attachments[0]
    assert attachment.connector.endpoint == "end"

    fixed_start = boundary.start
    area.center = Point(12, 8)
    canvas._update_attached_boundaries(area)
    assert boundary.start == fixed_start
    assert boundary.end_pose.point == Point(10, 8)
    assert boundary.length == pytest.approx(5)

    path = tmp_path / "restricted-joint.rct.json"
    save_project(canvas.project, path)
    loaded = load_project(path)
    assert len(loaded.restricted_attachments) == 1
    assert loaded.restricted_attachments[0].area_id == area.id
    assert loaded.restricted_attachments[0].connector == attachment.connector
    canvas.close()


def test_restricted_attachment_moves_curve_as_direct_joint():
    canvas = _canvas()
    area = PlanningObject("restricted_rectangle", Point(10, 8), 4, 2)
    curve = TrackElement("left", Point(8, 8), heading_deg=180,
                         radius=2, angle_deg=45, width=.1,
                         element_type="boundary")
    canvas.project.planning_objects.append(area)
    canvas.project.elements.append(curve)
    # Put the curve's start connector on the left contour and create the joint.
    curve.start = Point(8, 8)
    assert canvas._snap_boundary_to_restricted(curve)
    attachment = canvas.project.restricted_attachments[0]
    old_attached = curve.pose_at(attachment.connector.endpoint).point
    area.center = Point(11, 9)
    canvas._update_attached_boundaries(area)
    new_attached = curve.pose_at(attachment.connector.endpoint).point
    assert new_attached.x == pytest.approx(old_attached.x + 1)
    assert new_attached.y == pytest.approx(old_attached.y + 1)
    canvas.close()


def test_free_straight_endpoint_resizes_and_rotates_around_restricted_joint():
    canvas = _canvas()
    area = PlanningObject("restricted_rectangle", Point(10, 8), 4, 2)
    boundary = TrackElement("straight", Point(8, 8), heading_deg=180,
                            length=3, width=.1, element_type="boundary")
    canvas.project.planning_objects.append(area)
    canvas.project.elements.append(boundary)
    assert canvas._snap_boundary_to_restricted(boundary)
    attachment = canvas.project.restricted_attachments[0]
    assert attachment.connector.endpoint == "start"

    target = Point(6, 6)
    assert canvas._resize_free_connector_to(
        type(attachment.connector)(boundary.id, "end"), target,
        snap_values=False,
    )
    assert boundary.start == Point(8, 8)
    assert boundary.end_pose.point.x == pytest.approx(target.x)
    assert boundary.end_pose.point.y == pytest.approx(target.y)
    assert boundary.length == pytest.approx(hypot(2, 2))
    assert canvas.project.restricted_attachment_for(
        attachment.connector
    ) is not None
    canvas.close()


def test_curve_at_restricted_joint_resizes_like_curve_at_normal_joint():
    canvas = _canvas()
    area = PlanningObject("restricted_rectangle", Point(10, 8), 4, 2)
    curve = TrackElement("left", Point(8, 8), heading_deg=180,
                         radius=2, angle_deg=45, width=.1,
                         element_type="boundary")
    canvas.project.planning_objects.append(area)
    canvas.project.elements.append(curve)
    assert canvas._snap_boundary_to_restricted(curve)
    attachment = canvas.project.restricted_attachments[0]
    assert attachment.connector.endpoint == "start"
    fixed = curve.start_pose.point
    free = curve.end_pose.point
    dx, dy = free.x - fixed.x, free.y - fixed.y
    turn = radians(20)
    target = Point(
        fixed.x + dx * cos(turn) - dy * sin(turn),
        fixed.y + dx * sin(turn) + dy * cos(turn),
    )
    free_connector = ConnectorRef(curve.id, "end")
    assert canvas._resize_free_connector_to(
        free_connector, target, snap_values=False,
    )

    normal_canvas = _canvas()
    normal_curve = TrackElement("left", Point(8, 8), heading_deg=180,
                                radius=2, angle_deg=45, width=.1,
                                element_type="boundary")
    supporting_straight = TrackElement(
        "straight", Point(5, 8), heading_deg=0, length=3,
        width=.1, element_type="boundary",
    )
    normal_canvas.project.elements.extend([supporting_straight, normal_curve])
    normal_canvas.project.connect(
        ConnectorRef(normal_curve.id, "start"),
        ConnectorRef(supporting_straight.id, "end"),
    )
    assert normal_canvas._resize_free_connector_to(
        ConnectorRef(normal_curve.id, "end"), target, snap_values=False,
    )

    assert curve.start == normal_curve.start
    assert curve.heading_deg == pytest.approx(normal_curve.heading_deg)
    assert curve.radius == pytest.approx(normal_curve.radius)
    assert curve.angle_deg == pytest.approx(normal_curve.angle_deg)
    assert curve.end_pose.point.x == pytest.approx(normal_curve.end_pose.point.x)
    assert curve.end_pose.point.y == pytest.approx(normal_curve.end_pose.point.y)
    assert canvas.project.restricted_attachment_for(
        attachment.connector
    ) is not None
    normal_canvas.close()
    canvas.close()
