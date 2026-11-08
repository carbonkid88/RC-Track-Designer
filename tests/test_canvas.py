import os
from math import cos, hypot, isclose, radians, sin

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QContextMenuEvent, QFocusEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from rc_track_designer.canvas import TrackCanvas
from rc_track_designer.model import ConnectorRef, Point, TrackElement
from test_closure import rounded_open_loop


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


def test_escape_clears_selection_when_not_placing():
    app, canvas = make_canvas()
    element = TrackElement("straight", Point(4, 6), length=5)
    canvas.project.elements.append(element)
    canvas.selected = element
    canvas.selected_ids = {element.id}
    canvas.active_connector = ConnectorRef(element.id, "end")

    QTest.keyClick(canvas, Qt.Key.Key_Escape)

    assert canvas.selected is None
    assert canvas.selected_ids == set()
    assert canvas.active_connector is None
    canvas.close()


def test_escape_clears_newly_placed_free_element_on_first_press():
    app, canvas = make_canvas()
    canvas.set_placement("straight")
    position = canvas.world_to_screen(Point(5, 5)).toPoint()

    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=position)
    assert canvas.placement is None
    assert canvas.selected is not None

    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    assert canvas.selected is None
    assert canvas.selected_ids == set()
    canvas.close()


def test_middle_mouse_still_activates_pan():
    app, canvas = make_canvas()
    QTest.mousePress(canvas, Qt.MouseButton.MiddleButton, pos=QPoint(200, 200))
    assert canvas._panning is True
    QTest.mouseRelease(canvas, Qt.MouseButton.MiddleButton, pos=QPoint(200, 200))
    assert canvas._panning is False
    canvas.close()


def test_plain_arrow_keys_rotate_a_selected_segment_and_accept_auto_repeat():
    app, canvas = make_canvas()
    curve = TrackElement("left", Point(10, 8), heading_deg=20,
                         radius=3, angle_deg=40)
    canvas.project.elements.append(curve)
    canvas.selected = curve
    canvas.selected_ids = {curve.id}

    QTest.keyClick(canvas, Qt.Key.Key_Left)
    assert canvas.selected.heading_deg == 25
    QTest.keyClick(canvas, Qt.Key.Key_Right)
    assert canvas.selected.heading_deg == 20

    QTest.keyPress(canvas, Qt.Key.Key_Left)
    QTest.keyPress(canvas, Qt.Key.Key_Left)
    QTest.keyRelease(canvas, Qt.Key.Key_Left)
    assert canvas.selected.heading_deg == 30

    straight = TrackElement("straight", Point(4, 4), heading_deg=15)
    canvas.project.elements.append(straight)
    canvas.selected = straight
    canvas.selected_ids = {straight.id}
    QTest.keyClick(canvas, Qt.Key.Key_Left)
    assert canvas.selected.heading_deg == 20
    canvas.close()


def test_context_menu_can_delete_selected_segment_and_undo_restores_it():
    app, canvas = make_canvas()
    element = TrackElement("straight", Point(4, 5), length=5)
    canvas.project.elements.append(element)
    canvas.selected = element
    canvas.selected_ids = {element.id}

    menu = canvas._build_context_menu(None, None, can_delete=True)
    delete_action = next(action for action in menu.actions()
                         if action.text() == "Delete selection")
    delete_action.trigger()

    assert canvas.project.elements == []
    canvas.undo_stack.undo()
    assert len(canvas.project.elements) == 1
    assert canvas.project.elements[0].id == element.id
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


def test_neutral_curve_palette_appends_a_fitting_bend_direction():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(10, 8), heading_deg=0, length=5)
    canvas.project.elements.append(first)
    canvas.active_connector = ConnectorRef(first.id, "end")

    canvas.set_placement("curve", 40)

    added = canvas.project.elements[-1]
    assert added.kind in {"left", "right"}
    assert added.angle_deg == 40
    assert canvas.project.connection_for(ConnectorRef(first.id, "end")) is not None
    assert added.start_pose == first.end_pose
    canvas.close()


def test_snapping_distance_is_in_screen_pixels_and_aligns_tangent():
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
    assert canvas._snap_element(third)
    assert third.heading_deg == 0
    canvas.close()


def test_curve_can_snap_end_to_end_with_opposite_directed_tangents():
    app, canvas = make_canvas()
    canvas.project.hall_length = 30
    canvas.project.hall_width = 20
    target = TrackElement("right", Point(22.5, 11), heading_deg=0,
                          radius=1.5, angle_deg=90, width=2)
    moving = TrackElement("left", Point(22.5, 7.9), heading_deg=0,
                          radius=1.5, angle_deg=90, width=2)
    canvas.project.elements.extend([target, moving])

    assert canvas._snap_element(moving)

    connection = canvas.project.connection_for(ConnectorRef(moving.id, "end"))
    assert connection is not None
    assert {connection.first, connection.second} == {
        ConnectorRef(moving.id, "end"), ConnectorRef(target.id, "end")
    }
    assert isclose(moving.end_pose.point.x, target.end_pose.point.x, abs_tol=1e-9)
    assert isclose(moving.end_pose.point.y, target.end_pose.point.y, abs_tol=1e-9)
    canvas.project.validate_connections()
    canvas.close()


def test_snap_to_exact_track_area_margin_tolerates_float_rounding():
    app, canvas = make_canvas()
    canvas.project.hall_length = 25
    canvas.project.hall_width = 12
    target = TrackElement("left", Point(2.1, 11), heading_deg=180,
                          width=2, radius=1.1, angle_deg=90)
    straight = TrackElement("straight", Point(13.89771466168521,
                                               10.620253164556962),
                            heading_deg=180, width=2, length=11)
    canvas.project.elements.extend([target, straight])
    canvas.selected = straight
    canvas.selected_ids = {straight.id}
    canvas.scale = 30.24

    assert canvas._snap_element(straight)
    assert isclose(straight.end_pose.point.x, target.start.x, abs_tol=1e-9)
    assert isclose(straight.end_pose.point.y, target.start.y, abs_tol=1e-9)
    assert straight.end_pose.heading_deg == target.start_pose.heading_deg
    assert canvas.project.element_fits_hall(straight)
    assert len(canvas.project.connections) == 1
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


def test_hit_test_prefers_nearest_centerline_over_drawing_order():
    app, canvas = make_canvas()
    canvas.scale = 25
    intended = TrackElement("straight", Point(4, 6), length=8, width=2)
    neighbor = TrackElement("straight", Point(4, 6.9), length=8, width=2)
    canvas.project.elements.extend([intended, neighbor])
    click = canvas.world_to_screen(Point(8, 6.1))

    assert canvas._hit_test(click) is intended
    canvas.close()


def test_hit_test_keeps_selected_element_for_equal_overlapping_centerlines():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(4, 6), length=8, width=2)
    selected = TrackElement("straight", Point(4, 6), length=8, width=2)
    canvas.project.elements.extend([first, selected])
    canvas.selected = selected
    canvas.selected_ids = {selected.id}

    assert canvas._hit_test(canvas.world_to_screen(Point(8, 6))) is selected
    canvas.close()


def test_resize_target_uses_magnetic_distance_not_tiny_marker_hit_radius():
    app, canvas = make_canvas()
    canvas.scale = 25
    first = TrackElement("straight", Point(3, 6), length=4)
    target = TrackElement("straight", Point(9, 6), length=3)
    canvas.project.elements.extend([first, target])
    excluded = ConnectorRef(first.id, "end")
    pointer = canvas.world_to_screen(Point(8.2, 6))  # 20 px before target

    assert canvas._free_connector_at_excluding(pointer, excluded) is None
    assert canvas._free_connector_at_excluding(
        pointer, excluded, canvas.snap_distance_px
    ) == ConnectorRef(target.id, "start")
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


def test_strongly_rotated_curve_snaps_and_aligns_to_near_connector():
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

    assert canvas._snap_element(curve)
    assert curve.kind == "left"
    assert curve.start == target.point
    assert curve.heading_deg == target.heading_deg
    assert len(canvas.project.connections) == 1
    canvas.close()


def test_place_rotate_delete_and_properties_are_undoable():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(2, 2), length=5)
    canvas.project.elements.append(first); canvas.selected = first
    canvas.rotate_selected(5)
    assert canvas.selected.heading_deg == 5
    canvas.undo_stack.undo(); assert canvas.selected.heading_deg == 0
    canvas.undo_stack.redo(); assert canvas.selected.heading_deg == 5
    rotated_start = canvas.selected.start
    canvas.change_selected("property", x=4, length=8)
    assert canvas.selected.start.x == 4 and canvas.selected.length == 8
    canvas.undo_stack.undo(); assert canvas.selected.start == rotated_start and canvas.selected.length == 5
    canvas.delete_selected(); assert not canvas.project.elements
    canvas.undo_stack.undo(); assert len(canvas.project.elements) == 1
    canvas.close()


def test_curve_rotates_freely_around_midpoint():
    app, canvas = make_canvas()
    curve = TrackElement("left", Point(15, 10), heading_deg=0, radius=4, angle_deg=35)
    canvas.project.elements.append(curve)
    canvas.selected = curve
    canvas.selected_ids = {curve.id}
    pivot = curve.centerline_midpoint
    original_start = curve.start

    for _ in range(20):
        canvas.rotate_selected(5)

    assert canvas.selected.heading_deg == 100
    assert canvas.selected.start != original_start
    assert isclose(canvas.selected.centerline_midpoint.x, pivot.x, abs_tol=1e-9)
    assert isclose(canvas.selected.centerline_midpoint.y, pivot.y, abs_tol=1e-9)
    canvas.undo_stack.undo()
    assert canvas.selected.heading_deg == 95
    canvas.close()


def test_numeric_rotation_uses_the_same_centerline_pivot():
    app, canvas = make_canvas()
    curve = TrackElement("right", Point(15, 10), heading_deg=20, radius=3, angle_deg=50)
    canvas.project.elements.append(curve)
    canvas.selected = curve
    canvas.selected_ids = {curve.id}
    pivot = curve.centerline_midpoint

    canvas.change_selected("property", heading_deg=290)

    assert canvas.selected.heading_deg == 290
    assert isclose(canvas.selected.centerline_midpoint.x, pivot.x, abs_tol=1e-9)
    assert isclose(canvas.selected.centerline_midpoint.y, pivot.y, abs_tol=1e-9)
    canvas.undo_stack.undo()
    assert canvas.selected.heading_deg == 20
    canvas.close()


def test_curve_rotation_is_unrestricted_around_its_centerline_midpoint():
    app, canvas = make_canvas()
    curve = TrackElement("left", Point(15, 10), heading_deg=210, radius=3, angle_deg=35)
    canvas.project.elements.append(curve)
    canvas.selected = curve
    canvas.selected_ids = {curve.id}

    pivot = curve.centerline_midpoint
    assert canvas.manual_heading_allowed(curve, 300)
    assert canvas.manual_heading_allowed(curve, 120)
    assert canvas.manual_heading_allowed(curve, 305)
    assert canvas.manual_heading_allowed(curve, 115)
    canvas.change_selected("property", heading_deg=305)
    assert canvas.selected.heading_deg == 305
    assert isclose(canvas.selected.centerline_midpoint.x, pivot.x, abs_tol=1e-9)
    assert isclose(canvas.selected.centerline_midpoint.y, pivot.y, abs_tol=1e-9)
    assert canvas.undo_stack.count() == 1
    canvas.close()


def test_curve_angle_change_is_not_coupled_to_rotation():
    app, canvas = make_canvas()
    curve = TrackElement("left", Point(10, 8), heading_deg=310, radius=4, angle_deg=40)
    canvas.project.elements.append(curve)
    canvas.selected = curve
    canvas.selected_ids = {curve.id}

    canvas.change_selected("property", angle_deg=45)
    assert canvas.selected.angle_deg == 45
    assert canvas.selected.heading_deg == 310
    assert canvas.undo_stack.count() == 1
    canvas.close()


def test_length_change_keeps_connected_endpoint_and_extends_free_end():
    app, canvas = make_canvas()
    anchor = TrackElement("straight", Point(3, 6), length=4)
    extending = TrackElement("straight", anchor.end_pose.point,
                             anchor.end_pose.heading_deg, length=3)
    canvas.project.elements.extend([anchor, extending])
    canvas.project.connect(ConnectorRef(anchor.id, "end"), ConnectorRef(extending.id, "start"))
    canvas.selected = extending
    canvas.selected_ids = {extending.id}
    fixed_start = extending.start_pose

    canvas.change_selected("property", length=5.5)

    assert canvas.selected.start_pose == fixed_start
    assert canvas.selected.length == 5.5
    assert canvas.selected.end_pose.point.x == 12.5
    assert len(canvas.project.connections) == 1
    assert canvas.active_connector == ConnectorRef(extending.id, "end")
    canvas.undo_stack.undo()
    assert canvas.selected.length == 3
    assert len(canvas.project.connections) == 1
    canvas.close()


def test_length_change_with_connected_end_moves_only_free_start():
    app, canvas = make_canvas()
    anchor = TrackElement("straight", Point(10, 6), length=4)
    extending = TrackElement("straight", Point(7, 6), length=3)
    canvas.project.elements.extend([extending, anchor])
    canvas.project.connect(ConnectorRef(extending.id, "end"), ConnectorRef(anchor.id, "start"))
    canvas.selected = extending
    canvas.selected_ids = {extending.id}
    fixed_end = extending.end_pose

    canvas.change_selected("property", length=5)

    assert canvas.selected.end_pose == fixed_end
    assert canvas.selected.start == Point(5, 6)
    assert len(canvas.project.connections) == 1
    canvas.close()


def test_curve_radius_change_keeps_connected_endpoint():
    app, canvas = make_canvas()
    anchor = TrackElement("straight", Point(3, 6), length=4)
    curve = TrackElement("left", anchor.end_pose.point, radius=3, angle_deg=45)
    canvas.project.elements.extend([anchor, curve])
    canvas.project.connect(ConnectorRef(anchor.id, "end"), ConnectorRef(curve.id, "start"))
    canvas.selected = curve
    canvas.selected_ids = {curve.id}
    fixed_start = curve.start_pose

    canvas.change_selected("property", radius=4.5)

    assert canvas.selected.start_pose == fixed_start
    assert canvas.selected.radius == 4.5
    assert len(canvas.project.connections) == 1
    canvas.close()


def test_dragging_free_straight_connector_resizes_away_from_fixed_connection():
    app, canvas = make_canvas()
    anchor = TrackElement("straight", Point(3, 6), length=4)
    extending = TrackElement("straight", anchor.end_pose.point, length=3)
    canvas.project.elements.extend([anchor, extending])
    canvas.project.connect(ConnectorRef(anchor.id, "end"), ConnectorRef(extending.id, "start"))
    free = canvas.world_to_screen(extending.end_pose.point).toPoint()
    destination = canvas.world_to_screen(Point(12.2, 6)).toPoint()

    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=free)
    QTest.mouseMove(canvas, destination)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=destination)

    assert canvas.selected.length == 5.0
    assert canvas.selected.start == anchor.end_pose.point
    assert canvas.selected.end_pose.point == Point(12, 6)
    assert len(canvas.project.connections) == 1
    canvas.undo_stack.undo()
    assert canvas.selected.length == 3
    canvas.close()


def test_dragging_free_connector_to_compatible_target_closes_track():
    app, canvas = make_canvas()
    anchor = TrackElement("straight", Point(3, 6), length=4)
    extending = TrackElement("straight", anchor.end_pose.point, length=3)
    target = TrackElement("straight", Point(12, 6), length=3)
    canvas.project.elements.extend([anchor, extending, target])
    canvas.project.connect(ConnectorRef(anchor.id, "end"), ConnectorRef(extending.id, "start"))
    free = canvas.world_to_screen(extending.end_pose.point).toPoint()
    destination = canvas.world_to_screen(target.start).toPoint()

    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=free)
    QTest.mouseMove(canvas, destination)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=destination)

    assert extending.end_pose == target.start_pose
    assert len(canvas.project.connections) == 2
    assert not canvas.project.is_free(ConnectorRef(extending.id, "end"))
    canvas.undo_stack.undo()
    assert len(canvas.project.connections) == 1
    assert canvas.project.element_by_id(extending.id).length == 3
    canvas.close()


def test_dragging_curve_free_connector_adjusts_radius_and_angle():
    app, canvas = make_canvas()
    anchor = TrackElement("straight", Point(3, 6), length=4)
    curve = TrackElement("left", anchor.end_pose.point, radius=3, angle_deg=30)
    desired = TrackElement("left", anchor.end_pose.point, radius=4, angle_deg=45)
    canvas.project.elements.extend([anchor, curve])
    canvas.project.connect(ConnectorRef(anchor.id, "end"), ConnectorRef(curve.id, "start"))

    changed = canvas._resize_free_connector_to(
        ConnectorRef(curve.id, "end"), desired.end_pose.point
    )

    assert changed
    assert curve.start_pose == anchor.end_pose
    assert curve.radius == 4
    assert curve.angle_deg == 45
    assert len(canvas.project.connections) == 1
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


def test_guides_drag_from_rulers_snap_to_half_metres_and_are_undoable():
    app, canvas = make_canvas()
    start = QPoint(int(canvas.world_to_screen(Point(5.2, 0)).x()),
                   int(canvas.pan.y() - canvas._ruler_size / 2))
    destination = canvas.world_to_screen(Point(5.2, 5)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, destination)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=destination)
    assert canvas.project.guides_x == [5.0]

    canvas.undo_stack.undo()
    assert canvas.project.guides_x == []
    canvas.undo_stack.redo()
    assert canvas.project.guides_x == [5.0]

    guide_position = canvas.world_to_screen(Point(5, 5)).toPoint()
    moved_position = canvas.world_to_screen(Point(7.2, 5)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=guide_position)
    QTest.mouseMove(canvas, moved_position)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=moved_position)
    assert canvas.project.guides_x == [7.0]
    canvas.undo_stack.undo()
    assert canvas.project.guides_x == [5.0]
    canvas.close()


def test_guide_can_be_deleted_with_right_click_and_undo_restores_it():
    app, canvas = make_canvas()
    canvas.project.guides_y = [6.0]
    position = canvas.world_to_screen(Point(8, 6)).toPoint()
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, position,
                              canvas.mapToGlobal(position))

    QApplication.sendEvent(canvas, event)

    assert event.isAccepted()
    assert canvas.project.guides_y == []
    canvas.undo_stack.undo()
    assert canvas.project.guides_y == [6.0]
    canvas.undo_stack.redo()
    assert canvas.project.guides_y == []
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


def test_rotation_may_overlap_neighbor_and_releases_connection():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(2, 4), length=5)
    second = TrackElement("straight", first.end_pose.point, first.end_pose.heading_deg, length=5)
    canvas.project.elements.extend([first, second])
    canvas.project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    canvas.selected = second
    canvas.selected_ids = {second.id}

    canvas.rotate_selected(5)
    restored = canvas.project.element_by_id(second.id)
    assert restored.heading_deg == 5
    assert len(canvas.project.connections) == 0
    assert canvas.overlapping_element_ids() == {first.id, second.id}
    assert canvas.undo_stack.count() == 1
    canvas.undo_stack.undo()
    assert len(canvas.project.connections) == 1
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


def test_overlapping_standalone_placement_is_allowed_and_marked():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(5, 5), length=8, width=2)
    canvas.project.elements.append(first)
    canvas.set_placement("straight")
    overlap_position = canvas.world_to_screen(Point(7, 5)).toPoint()
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=overlap_position)
    assert len(canvas.project.elements) == 2
    assert canvas.overlapping_element_ids() == {
        element.id for element in canvas.project.elements
    }
    canvas.close()


def test_drag_allows_overlap_and_marks_both_elements():
    app, canvas = make_canvas()
    stationary = TrackElement("straight", Point(15, 8), length=5, width=2)
    moving = TrackElement("straight", Point(5, 8), length=5, width=2)
    canvas.project.elements.extend([stationary, moving])
    midpoint = canvas.world_to_screen(Point(7.5, 8)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=midpoint)
    QTest.mouseMove(canvas, midpoint + QPoint(int(8 * canvas.scale), 0))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=midpoint + QPoint(int(8 * canvas.scale), 0))
    moved = canvas.project.element_by_id(moving.id)
    assert moved.end_pose.point.x > stationary.start.x
    assert canvas.overlapping_element_ids() == {moving.id, stationary.id}
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


def test_copy_paste_group_preserves_internal_connections_and_is_undoable():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(4, 6), length=4)
    second = TrackElement("left", first.end_pose.point, first.end_pose.heading_deg,
                          radius=3, angle_deg=45)
    canvas.project.elements.extend([first, second])
    canvas.project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    canvas.selected = second
    canvas.selected_ids = {first.id, second.id}

    canvas.copy_selected()
    canvas.paste_copied()

    assert len(canvas.project.elements) == 4
    assert len(canvas.project.connections) == 2
    assert len(canvas.selected_ids) == 2
    assert not ({first.id, second.id} & canvas.selected_ids)
    pasted = [item for item in canvas.project.elements if item.id in canvas.selected_ids]
    assert {round(item.start.x - source.start.x, 6)
            for item, source in zip(pasted, (first, second))} == {0.5}
    canvas.undo_stack.undo()
    assert len(canvas.project.elements) == 2
    assert len(canvas.project.connections) == 1
    canvas.undo_stack.redo()
    assert len(canvas.project.elements) == 4
    canvas.close()


def test_copy_single_element_does_not_copy_external_connection():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(4, 6), length=4)
    second = TrackElement("straight", first.end_pose.point, length=4)
    canvas.project.elements.extend([first, second])
    canvas.project.connect(ConnectorRef(first.id, "end"), ConnectorRef(second.id, "start"))
    canvas.selected = first
    canvas.selected_ids = {first.id}

    canvas.copy_selected()
    canvas.paste_copied()

    assert len(canvas.project.elements) == 3
    assert len(canvas.project.connections) == 1
    canvas.close()


def test_connected_selection_snaps_as_rigid_group_to_external_connector():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(3, 5), length=4)
    second = TrackElement("straight", first.end_pose.point, length=3)
    target = TrackElement("straight", Point(10.5, 5.3), heading_deg=30, length=3)
    canvas.project.elements.extend([first, second, target])
    canvas.project.connect(ConnectorRef(first.id, "end"),
                           ConnectorRef(second.id, "start"))
    canvas.selected = second
    canvas.selected_ids = {first.id, second.id}

    assert canvas._snap_group()
    assert len(canvas.project.connections) == 2
    assert first.end_pose == second.start_pose
    assert second.end_pose == target.start_pose
    assert isclose(first.heading_deg, 30, abs_tol=1e-9)
    assert isclose(second.heading_deg, 30, abs_tol=1e-9)
    canvas.close()


def test_apply_track_closure_is_one_undoable_command():
    app, canvas = make_canvas()
    project, first, second = rounded_open_loop()
    canvas.set_project(project)
    canvas.toggle_closure_connector(first)
    canvas.toggle_closure_connector(second)
    proposal = canvas.prepare_track_closure()

    assert proposal is not None
    canvas.apply_track_closure(proposal)
    assert len(canvas.project.connections) == len(canvas.project.elements)
    assert canvas.undo_stack.count() == 1
    canvas.undo_stack.undo()
    assert len(canvas.project.connections) == len(canvas.project.elements) - 1
    canvas.undo_stack.redo()
    assert len(canvas.project.connections) == len(canvas.project.elements)
    canvas.close()


def test_context_menu_requests_close_when_two_connectors_are_marked():
    app, canvas = make_canvas()
    first = TrackElement("straight", Point(3, 5), length=3)
    second = TrackElement("straight", Point(12, 5), length=3)
    canvas.project.elements.extend([first, second])
    canvas.toggle_closure_connector(ConnectorRef(first.id, "start"))
    canvas.toggle_closure_connector(ConnectorRef(second.id, "end"))
    spy = QSignalSpy(canvas.close_track_requested)
    menu = canvas._build_context_menu(None, None)

    assert menu is not None
    assert menu.actions()[0].text() == "Close track…"
    menu.actions()[0].trigger()

    assert spy.count() == 1
    canvas.close()


def test_curve_radius_change_cannot_create_self_intersecting_road_shape():
    app, canvas = make_canvas()
    curve = TrackElement("left", Point(5, 5), width=2, radius=3, angle_deg=45)
    canvas.project.elements.append(curve)
    canvas.selected = curve
    canvas.selected_ids = {curve.id}

    canvas.change_selected("Invalid radius", radius=0.5)

    restored = canvas.project.element_by_id(curve.id)
    assert restored.radius == 3
    assert restored.has_valid_road_geometry
    assert canvas.undo_stack.count() == 0
    canvas.close()


def test_free_curve_connector_resize_rejects_radius_inside_road_width():
    app, canvas = make_canvas()
    lead = TrackElement("straight", Point(2, 5), length=3, width=2)
    curve = TrackElement("left", lead.end_pose.point, radius=3, angle_deg=45, width=2)
    canvas.project.elements.extend((lead, curve))
    canvas.project.connect(ConnectorRef(lead.id, "end"), ConnectorRef(curve.id, "start"))
    original_end = curve.end_pose
    invalid_target = TrackElement(
        "left", curve.start, curve.heading_deg, width=curve.width,
        radius=0.5, angle_deg=45,
    ).end_pose.point

    assert not canvas._resize_free_connector_to(
        ConnectorRef(curve.id, "end"), invalid_target, snap_values=False
    )
    assert curve.radius == 3
    assert curve.end_pose == original_end
    canvas.close()
