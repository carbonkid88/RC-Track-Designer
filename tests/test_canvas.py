import os
from math import cos, hypot, isclose, radians, sin

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rc_track_designer.canvas import TrackCanvas
from rc_track_designer.model import ConnectorRef, Point, TrackElement


def make_canvas():
    app = QApplication.instance() or QApplication([])
    canvas = TrackCanvas()
    canvas.resize(800, 600)
    canvas.show()
    canvas.setFocus()
    app.processEvents()
    return app, canvas


def test_space_and_left_mouse_activate_pan_without_invalid_modifier_enum():
    app, canvas = make_canvas()
    original_pan = QPointF(canvas.pan)
    QTest.keyPress(canvas, Qt.Key.Key_Space)
    assert canvas._space_pressed is True
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(300, 250))
    assert canvas._panning is True
    QTest.mouseMove(canvas, QPoint(320, 270))
    assert canvas.pan != original_pan
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(320, 270))
    QTest.keyRelease(canvas, Qt.Key.Key_Space)
    assert canvas._panning is False
    assert canvas._space_pressed is False
    canvas.close()


def test_middle_mouse_still_activates_pan():
    app, canvas = make_canvas()
    QTest.mousePress(canvas, Qt.MouseButton.MiddleButton, pos=QPoint(200, 200))
    assert canvas._panning is True
    QTest.mouseRelease(canvas, Qt.MouseButton.MiddleButton, pos=QPoint(200, 200))
    assert canvas._panning is False
    canvas.close()


def test_normal_left_mouse_keeps_element_selection_and_dragging():
    app, canvas = make_canvas()
    element = TrackElement("straight", Point(5, 5), length=8)
    canvas.project.elements.append(element)
    position = canvas.world_to_screen(Point(7, 5)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=position)
    assert canvas.selected is element
    assert canvas._dragging_element is True
    assert canvas._panning is False
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=position)
    canvas.close()


def test_focus_loss_resets_space_pan_and_element_drag_state():
    app, canvas = make_canvas()
    canvas._space_pressed = True
    canvas._panning = True
    canvas._dragging_element = True
    event = QFocusEvent(QFocusEvent.Type.FocusOut)
    QApplication.sendEvent(canvas, event)
    assert canvas._space_pressed is False
    assert canvas._panning is False
    assert canvas._dragging_element is False
    canvas.close()


def test_world_scale_is_consistent_for_hall_and_track_dimensions():
    app, canvas = make_canvas()
    origin = canvas.world_to_screen(Point(0, 0))
    one_metre_x = canvas.world_to_screen(Point(1, 0))
    one_metre_y = canvas.world_to_screen(Point(0, 1))
    assert isclose(abs(one_metre_x.x() - origin.x()), canvas.scale)
    assert isclose(abs(one_metre_y.y() - origin.y()), canvas.scale)
    element = TrackElement("straight", Point(0, 0), length=5, width=2)
    start = canvas.world_to_screen(element.start)
    end = canvas.world_to_screen(element.end_pose.point)
    assert isclose(abs(end.x() - start.x()), 5 * canvas.scale)
    assert isclose(element.width * canvas.scale, 2 * canvas.scale)
    canvas.close()


def test_active_end_connector_appends_and_advances_to_new_free_end():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(2, 3), heading_deg=20, length=5)
    canvas.project.elements.append(first)
    canvas.active_connector = ConnectorRef(first.id, "end")
    canvas.set_placement("left", 45)
    assert len(canvas.project.elements) == 2
    added = canvas.project.elements[-1]
    assert canvas.project.connection_for(ConnectorRef(first.id, "end")) is not None
    assert added.start_pose == first.end_pose
    assert canvas.active_connector == ConnectorRef(added.id, "end")
    canvas.undo_stack.undo()
    assert len(canvas.project.elements) == 1
    assert canvas.active_connector == ConnectorRef(first.id, "end")
    canvas.undo_stack.redo()
    assert len(canvas.project.elements) == 2
    canvas.close()


def test_active_start_connector_appends_backwards_and_advances_to_new_start():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(10, 8), heading_deg=35, length=5)
    canvas.project.elements.append(first)
    canvas.active_connector = ConnectorRef(first.id, "start")
    canvas.set_placement("right", 30)
    added = canvas.project.elements[-1]
    assert added.end_pose == first.start_pose
    assert canvas.active_connector == ConnectorRef(added.id, "start")
    canvas.close()


def test_snapping_distance_is_in_screen_pixels_and_checks_tangent():
    app, canvas = make_canvas()
    for scale in (5.0, 50.0):
        canvas.scale = scale
        canvas.project.elements.clear(); canvas.project.connections.clear()
        first = TrackElement("straight", Point(1, 2), heading_deg=0, length=5)
        gap_world = 10 / canvas.scale
        second = TrackElement("straight", Point(6 + gap_world, 2), heading_deg=5, length=3)
        canvas.project.elements.extend([first, second])
        assert canvas._snap_element(second)
        assert second.start_pose == first.end_pose
        assert len(canvas.project.connections) == 1
    third = TrackElement("straight", Point(9, 2), heading_deg=90, length=2)
    canvas.project.elements.append(third)
    assert not canvas._snap_element(third)
    canvas.close()


def test_small_curve_body_is_draggable_outside_connector_hit_radius():
    app, canvas = make_canvas()
    canvas.scale = 25
    curve = TrackElement("left", Point(8, 5), radius=1, angle_deg=90, width=0.5)
    canvas.project.elements.append(curve)
    body = curve.centerline_points()[len(curve.centerline_points()) // 2]
    position = canvas.world_to_screen(body).toPoint()

    assert canvas._connector_at(position) is None
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=position)
    assert canvas._dragging_element is True
    QTest.mouseMove(canvas, position + QPoint(30, -20))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=position + QPoint(30, -20))
    assert canvas.project.element_by_id(curve.id).start != Point(8, 5)
    canvas.close()


def test_curve_uses_exact_arc_path_with_correct_endpoints():
    app, canvas = make_canvas()
    curve = TrackElement("right", Point(10, 8), heading_deg=25, radius=3, angle_deg=90)
    path = canvas._element_path(curve)
    start = path.pointAtPercent(0)
    expected_start = canvas.world_to_screen(curve.start)
    assert hypot(start.x() - expected_start.x(), start.y() - expected_start.y()) < 0.05
    # Move + two cubic arc sections, but no extra LineTo join.
    assert path.elementCount() == 7
    end = path.pointAtPercent(1)
    expected = canvas.world_to_screen(curve.end_pose.point)
    assert hypot(end.x() - expected.x(), end.y() - expected.y()) < 0.05
    canvas.close()


def test_large_curve_rendering_uses_the_collision_contour_without_pen_halo():
    app, canvas = make_canvas()
    canvas.scale = 30
    for angle in (75, 80, 85, 90):
        curve = TrackElement("left", Point(8, 6), radius=4, angle_deg=angle, width=2)
        road = canvas._road_shape(curve)
        assert not road.isEmpty()
        assert road.contains(canvas.world_to_screen(curve.centerline_points()[len(curve.centerline_points()) // 2]))
        assert road.boundingRect().width() > curve.radius * canvas.scale
        assert road.boundingRect().height() > curve.radius * canvas.scale
    canvas.close()


def test_manual_snap_range_is_noticeable_but_not_overly_aggressive():
    app, canvas = make_canvas()
    canvas.scale = 25
    first = TrackElement("left", Point(5, 5), radius=4, angle_deg=45)
    target = first.end_pose
    gap = 32 / canvas.scale
    second = TrackElement("right", Point(target.point.x + gap * cos(radians(target.heading_deg)),
                                         target.point.y + gap * sin(radians(target.heading_deg))),
                          heading_deg=target.heading_deg, radius=4, angle_deg=45)
    canvas.project.elements.extend([first, second])

    assert canvas._snap_element(second)
    assert second.start_pose == first.end_pose
    assert len(canvas.project.connections) == 1
    canvas.close()


def test_strongly_rotated_curve_does_not_snap_back_to_old_tangent():
    app, canvas = make_canvas()
    canvas.scale = 25
    straight = TrackElement("straight", Point(3, 5), heading_deg=15, length=5)
    target = straight.end_pose
    curve = TrackElement(
        "left",
        Point(target.point.x + 1, target.point.y),
        heading_deg=(target.heading_deg + 170) % 360,
        radius=4,
        angle_deg=45,
    )
    canvas.project.elements.extend([straight, curve])

    original_start = curve.start
    original_heading = curve.heading_deg
    assert not canvas._snap_element(curve)
    assert curve.kind == "left"
    assert curve.start == original_start
    assert curve.heading_deg == original_heading
    assert len(canvas.project.connections) == 0
    canvas.close()


def test_place_rotate_delete_and_properties_are_undoable():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(2, 2), length=5)
    canvas.project.elements.append(first); canvas.selected = first
    canvas.rotate_selected(5)
    assert canvas.selected.heading_deg == 5
    canvas.undo_stack.undo(); assert canvas.selected.heading_deg == 0
    canvas.undo_stack.redo(); assert canvas.selected.heading_deg == 5
    canvas.change_selected("property", x=4, length=8)
    assert canvas.selected.start.x == 4 and canvas.selected.length == 8
    canvas.undo_stack.undo(); assert canvas.selected.start.x == 2 and canvas.selected.length == 5
    canvas.delete_selected(); assert not canvas.project.elements
    canvas.undo_stack.undo(); assert len(canvas.project.elements) == 1
    canvas.close()


def test_curve_manual_rotation_is_limited_symmetrically_by_curve_angle():
    app, canvas = make_canvas()
    curve = TrackElement("left", Point(5, 5), heading_deg=50, radius=4, angle_deg=40)
    canvas.project.elements.append(curve)
    canvas.selected = curve
    canvas.selected_ids = {curve.id}
    canvas.rotate_selected(5)
    assert curve.heading_deg == 50
    assert canvas.undo_stack.count() == 0

    curve.heading_deg = 45
    canvas.rotate_selected(5)
    assert canvas.selected.heading_deg == 50
    canvas.undo_stack.undo()
    assert canvas.selected.heading_deg == 45

    canvas.selected.heading_deg = 315
    canvas.rotate_selected(-5)
    assert canvas.selected.heading_deg == 310
    canvas.rotate_selected(-5)
    assert canvas.selected.heading_deg == 310

    right = TrackElement("right", Point(10, 10), heading_deg=300, radius=4, angle_deg=30)
    canvas.project.elements.append(right)
    canvas.selected = right
    canvas.selected_ids = {right.id}
    canvas.rotate_selected(-5)
    assert right.heading_deg == 300
    right.heading_deg = 305
    canvas.rotate_selected(-5)
    assert canvas.selected.heading_deg == 300
    right.heading_deg = 55
    canvas.rotate_selected(5)
    assert canvas.selected.heading_deg == 60
    canvas.rotate_selected(5)
    assert canvas.selected.heading_deg == 60

    straight = TrackElement("straight", Point(12, 5), heading_deg=20)
    canvas.project.elements.append(straight)
    canvas.selected = straight
    canvas.selected_ids = {straight.id}
    canvas.rotate_selected(5)
    assert canvas.selected.heading_deg == 25
    assert canvas.undo_stack.count() == 4
    canvas.close()


def test_curve_angle_change_cannot_exceed_combined_ninety_degrees():
    app, canvas = make_canvas()
    curve = TrackElement("left", Point(5, 5), heading_deg=50, radius=4, angle_deg=40)
    canvas.project.elements.append(curve)
    canvas.selected = curve
    canvas.selected_ids = {curve.id}

    canvas.change_selected("property", angle_deg=45)
    assert canvas.selected.angle_deg == 40
    assert canvas.selected.heading_deg == 50
    assert canvas.undo_stack.count() == 0
    canvas.close()


def test_rubber_band_selects_multiple_elements_for_group_move():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(5, 6), length=4, width=1)
    second = TrackElement("left", Point(12, 6), radius=2, angle_deg=45, width=1)
    outside = TrackElement("straight", Point(22, 14), length=2, width=1)
    canvas.project.elements.extend([first, second, outside])
    start = canvas.world_to_screen(Point(3, 3)).toPoint()
    end = canvas.world_to_screen(Point(17, 9)).toPoint()

    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, end)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
    assert canvas.selected_ids == {first.id, second.id}

    first_start, second_start = first.start, second.start
    first_midpoint = canvas.world_to_screen(Point(7, 6)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=first_midpoint)
    QTest.mouseMove(canvas, first_midpoint + QPoint(0, -30))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=first_midpoint + QPoint(0, -30))
    assert first.start != first_start
    assert second.start != second_start
    assert outside.start == Point(22, 14)
    canvas.close()


def test_dragging_connected_element_disconnects_only_it_and_undo_restores_connection():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(2, 4), length=5)
    second = TrackElement("straight", first.end_pose.point, first.end_pose.heading_deg, length=5)
    canvas.project.elements.extend([first, second])
    canvas.project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    original_first = first.start
    original_second = second.start
    midpoint = canvas.world_to_screen(Point(second.start.x + 2.5, second.start.y)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=midpoint)
    QTest.mouseMove(canvas, midpoint + QPoint(80, 60))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=midpoint + QPoint(80, 60))
    assert canvas.project.connections == []
    assert canvas.project.element_by_id(first.id).start == original_first
    assert canvas.project.element_by_id(second.id).start != original_second
    canvas.undo_stack.undo()
    assert len(canvas.project.connections) == 1
    assert canvas.project.element_by_id(first.id).start == original_first
    assert canvas.project.element_by_id(second.id).start == original_second
    canvas.close()


def test_deleting_connected_element_and_undo_restore_connection():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(1, 3), length=5)
    second = TrackElement("straight", first.end_pose.point, first.end_pose.heading_deg)
    canvas.project.elements.extend([first, second])
    canvas.project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    canvas.selected = second
    canvas.delete_selected()
    assert len(canvas.project.elements) == 1
    assert canvas.project.is_free(ConnectorRef(first.id, "end"))
    canvas.undo_stack.undo()
    assert len(canvas.project.elements) == 2
    assert len(canvas.project.connections) == 1
    canvas.close()


def test_connection_can_be_disconnected_explicitly_and_undo_restores_it():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(2, 4), length=5)
    second = TrackElement("straight", first.end_pose.point, first.end_pose.heading_deg, length=5)
    connector = ConnectorRef(first.id, "end")
    canvas.project.elements.extend([first, second])
    canvas.project.connect(connector, ConnectorRef(second.id, "start"))

    assert canvas.disconnect_connector(connector)
    assert canvas.project.connections == []
    assert canvas.active_connector == connector
    canvas.undo_stack.undo()
    assert len(canvas.project.connections) == 1
    assert canvas.active_connector is None
    canvas.undo_stack.redo()
    assert canvas.project.connections == []
    assert canvas.active_connector == connector
    canvas.close()


def test_double_click_on_connected_marker_disconnects_it():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(2, 4), length=5)
    second = TrackElement("straight", first.end_pose.point, first.end_pose.heading_deg, length=5)
    canvas.project.elements.extend([first, second])
    canvas.project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    marker = canvas.world_to_screen(first.end_pose.point).toPoint()

    QTest.mouseDClick(canvas, Qt.MouseButton.LeftButton, pos=marker)
    assert canvas.project.connections == []
    assert canvas.active_connector is not None
    canvas.close()


def test_rotation_that_would_overlap_neighbor_is_rejected_and_connection_preserved():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(2, 4), length=5)
    second = TrackElement("straight", first.end_pose.point, first.end_pose.heading_deg, length=5)
    canvas.project.elements.extend([first, second])
    canvas.project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    canvas.selected = second
    canvas.selected_ids = {second.id}

    canvas.rotate_selected(5)
    restored = canvas.project.element_by_id(second.id)
    assert restored.heading_deg == 0
    assert len(canvas.project.connections) == 1
    assert canvas.undo_stack.count() == 0
    canvas.close()


def test_append_is_blocked_when_complete_road_would_leave_hall():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(24, 10), heading_deg=0, length=5, width=2)
    canvas.project.elements.append(first)
    canvas.active_connector = ConnectorRef(first.id, "end")
    canvas.set_placement("straight")
    assert len(canvas.project.elements) == 1
    assert canvas.active_connector == ConnectorRef(first.id, "end")
    canvas.close()


def test_drag_is_visibly_clamped_at_hall_boundary_and_undo_restores_connection():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(2, 4), length=5)
    second = TrackElement("straight", first.end_pose.point, first.end_pose.heading_deg, length=5)
    canvas.project.elements.extend([first, second])
    canvas.project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    original_second = second.start
    midpoint = canvas.world_to_screen(Point(second.start.x + 2.5, second.start.y)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=midpoint)
    QTest.mouseMove(canvas, QPoint(canvas.width() + 300, midpoint.y()))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(canvas.width() + 300, midpoint.y()))
    moved = canvas.project.element_by_id(second.id)
    assert moved.start != original_second
    assert canvas.project.element_fits_hall(moved)
    assert len(canvas.project.connections) == 0
    canvas.undo_stack.undo()
    restored = canvas.project.element_by_id(second.id)
    assert restored.start == original_second
    assert len(canvas.project.connections) == 1
    canvas.close()


def test_overlapping_standalone_placement_is_blocked():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(5, 5), length=8, width=2)
    canvas.project.elements.append(first)
    canvas.set_placement("straight")
    overlap_position = canvas.world_to_screen(Point(7, 5)).toPoint()
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=overlap_position)
    assert len(canvas.project.elements) == 1
    canvas.close()


def test_drag_stops_before_overlapping_another_element():
    app, canvas = make_canvas()
    stationary = TrackElement("straight", Point(15, 8), length=5, width=2)
    moving = TrackElement("straight", Point(5, 8), length=5, width=2)
    canvas.project.elements.extend([stationary, moving])
    midpoint = canvas.world_to_screen(Point(7.5, 8)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=midpoint)
    QTest.mouseMove(canvas, midpoint + QPoint(int(8 * canvas.scale), 0))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=midpoint + QPoint(int(8 * canvas.scale), 0))
    moved = canvas.project.element_by_id(moving.id)
    assert moved.end_pose.point.x <= stationary.start.x
    intersection = canvas._road_shape(moved).intersected(canvas._road_shape(stationary)).boundingRect()
    assert intersection.width() * intersection.height() < 1e-6
    canvas.close()


def test_curve_can_be_dragged_out_of_an_existing_overlap():
    app, canvas = make_canvas()
    stationary = TrackElement("straight", Point(5, 8), length=8, width=2)
    curve = TrackElement("left", Point(8, 8), radius=2, angle_deg=90, width=2)
    canvas.project.elements.extend([stationary, curve])
    canvas.selected = curve
    canvas.selected_ids = {curve.id}
    canvas._remember_initial_overlaps()
    pair = frozenset((stationary.id, curve.id))
    assert pair in canvas._drag_ignored_pairs

    moved = canvas._move_selection_safely(0, 4)
    canvas._forget_resolved_overlaps()
    assert moved == (0, 4)
    assert curve.start == Point(8, 12)
    assert pair not in canvas._drag_ignored_pairs
    canvas.close()


def test_shift_multiselect_moves_connected_group_and_preserves_internal_connection():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(4, 6), length=5)
    second = TrackElement("straight", first.end_pose.point, first.end_pose.heading_deg, length=5)
    canvas.project.elements.extend([first, second])
    canvas.project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    first_mid = canvas.world_to_screen(Point(6.5, 6)).toPoint()
    second_mid = canvas.world_to_screen(Point(11.5, 6)).toPoint()
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=first_mid)
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, pos=second_mid)
    assert canvas.selected_ids == {first.id, second.id}
    before_first, before_second = first.start, second.start
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=second_mid)
    QTest.mouseMove(canvas, second_mid + QPoint(0, -50))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=second_mid + QPoint(0, -50))
    moved_first = canvas.project.element_by_id(first.id)
    moved_second = canvas.project.element_by_id(second.id)
    assert moved_first.start.y > before_first.y
    assert moved_second.start.y > before_second.y
    assert len(canvas.project.connections) == 1
    assert moved_first.end_pose == moved_second.start_pose
    canvas.undo_stack.undo()
    assert canvas.project.element_by_id(first.id).start == before_first
    assert canvas.project.element_by_id(second.id).start == before_second
    canvas.close()
