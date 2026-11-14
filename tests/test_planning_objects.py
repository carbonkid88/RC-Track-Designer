import json
import os
from copy import deepcopy
from math import cos, hypot, radians, sin

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rc_track_designer.canvas import TrackCanvas
from rc_track_designer.i18n import TranslationManager
from rc_track_designer.model import PlanningObject, Point, TrackElement, TrackProject
from rc_track_designer.planning import draw_planning_object
from rc_track_designer.printing import (
    PrintOptions, pdf_printer, render_project, render_project_to_printer,
)
from rc_track_designer.storage import FORMAT_VERSION, load_project, save_project
from rc_track_designer.ui import MainWindow


@pytest.fixture(scope="module", autouse=True)
def application():
    yield QApplication.instance() or QApplication([])


def _canvas(mode="normal"):
    canvas = TrackCanvas()
    canvas.resize(900, 650)
    canvas.set_project(TrackProject(30, 20, editor_mode=mode))
    canvas.show()
    QApplication.processEvents()
    return canvas


@pytest.mark.parametrize("mode", ["normal", "indoor"])
@pytest.mark.parametrize("kind", ["start_finish", "timing_loop"])
def test_both_markers_can_be_inserted_in_both_modes(mode, kind):
    canvas = _canvas(mode)
    canvas.set_planning_placement(kind, 2.4)
    QTest.mouseClick(
        canvas, Qt.MouseButton.LeftButton,
        pos=canvas.world_to_screen(Point(10, 8)).toPoint(),
    )
    assert len(canvas.project.planning_objects) == 0
    QTest.mouseMove(
        canvas, canvas.world_to_screen(Point(10, 10.4)).toPoint(),
    )
    QTest.mouseClick(
        canvas, Qt.MouseButton.LeftButton,
        pos=canvas.world_to_screen(Point(10, 10.4)).toPoint(),
    )
    assert len(canvas.project.planning_objects) == 1
    item = canvas.project.planning_objects[0]
    assert item.kind == kind
    # QTest delivers integer screen coordinates, so allow one pixel of rounding.
    assert item.length == pytest.approx(2.4, abs=1 / canvas.scale)
    assert item.width == pytest.approx(0.1)
    assert item.heading_deg == pytest.approx(0.0)
    canvas.close()


def test_marker_move_rotate_delete_and_undo_redo():
    canvas = _canvas()
    item = PlanningObject("start_finish", Point(10, 8), length=2)
    canvas.project.planning_objects.append(item)
    center = canvas.world_to_screen(item.center).toPoint()
    target = center + QPoint(50, -25)

    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=center)
    QTest.mouseMove(canvas, target)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)
    assert item.center.x == pytest.approx(12, abs=0.1)
    moved_center = item.center
    canvas.rotate_selected(5)
    assert canvas.selected_planning.heading_deg == pytest.approx(5)
    canvas.undo_stack.undo()
    assert canvas.selected_planning.heading_deg == pytest.approx(0)
    canvas.undo_stack.undo()
    assert canvas.project.planning_objects[0].center != moved_center
    canvas.undo_stack.redo()
    canvas.undo_stack.redo()
    assert canvas.selected_planning.heading_deg == pytest.approx(5)
    canvas.delete_selected()
    assert not canvas.project.planning_objects
    canvas.undo_stack.undo()
    assert len(canvas.project.planning_objects) == 1
    canvas.close()


def test_locked_marker_stays_selectable_but_cannot_move_rotate_or_edit():
    canvas = _canvas()
    item = PlanningObject("timing_loop", Point(10, 8), locked=True)
    canvas.project.planning_objects.append(item)
    center = canvas.world_to_screen(item.center).toPoint()
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=center)
    assert canvas.selected_planning is item
    before = deepcopy(item)
    canvas.rotate_selected(5)
    canvas.change_selected("change", x=15, length=4)
    assert item == before
    canvas.toggle_selected_planning_lock()
    assert not canvas.selected_planning.locked
    canvas.undo_stack.undo()
    assert canvas.selected_planning.locked
    canvas.close()


def test_numeric_marker_properties_are_editable_in_properties_panel():
    window = MainWindow()
    item = PlanningObject("start_finish", Point(8, 7), length=2)
    window.canvas.project.planning_objects.append(item)
    window.canvas.selected_planning = item
    window._selection_changed(item)

    window.property_spins["length"].setValue(3.5)
    window.property_spins["x"].setValue(9.0)
    window.property_spins["heading_deg"].setValue(30.0)
    assert window.canvas.selected_planning.length == pytest.approx(3.5)
    assert window.canvas.selected_planning.center.x == pytest.approx(9.0)
    assert window.canvas.selected_planning.heading_deg == pytest.approx(30.0)

    window.canvas.selected_planning.locked = True
    window._selection_changed(window.canvas.selected_planning)
    assert not window.property_spins["length"].isEnabled()
    assert window.element_type_value.text() == "Start-/Ziellinie"
    window.dirty = False
    window.close()


def test_format_6_roundtrip_preserves_multiple_marker_types_and_lock(tmp_path):
    project = TrackProject(30, 20, planning_objects=[
        PlanningObject("start_finish", Point(5, 6), length=2.5, heading_deg=15),
        PlanningObject("timing_loop", Point(12, 9), length=3, locked=True),
    ])
    path = tmp_path / "markers.rct.json"
    save_project(project, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    loaded = load_project(path)
    assert FORMAT_VERSION == raw["format_version"] == 6
    assert loaded == project
    assert len(raw["planning_objects"]) == 2


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_old_project_formats_load_without_synthetic_markers(tmp_path, version):
    path = tmp_path / f"v{version}.rct.json"
    path.write_text(json.dumps({
        "format": "rc-track-designer",
        "format_version": version,
        "hall": {"length": 30, "width": 20},
        "elements": [],
        "connections": [],
    }), encoding="utf-8")
    assert load_project(path).planning_objects == []


def test_vector_rendering_draws_checkerboard_and_green_loop_at_any_scale():
    for scale in (20.0, 100.0):
        image = QImage(500, 300, QImage.Format.Format_ARGB32)
        image.fill(QColor("#dddddd"))
        painter = QPainter(image)
        mapper = lambda point, s=scale: QPoint(250 + round(point.x * s),
                                               150 - round(point.y * s))
        draw_planning_object(
            painter, PlanningObject("start_finish", Point(0, 0), length=2),
            mapper, scale,
        )
        draw_planning_object(
            painter, PlanningObject("timing_loop", Point(1.5, 0), length=2),
            mapper, scale,
        )
        painter.end()
        colors = {image.pixelColor(x, y).name()
                  for x in range(image.width()) for y in range(image.height())}
        assert "#111111" in colors
        assert "#ffffff" in colors
        assert "#24a148" in colors


def test_markers_are_in_print_output_but_selection_outline_is_not():
    item = PlanningObject("timing_loop", Point(10, 8), length=3)
    project = TrackProject(20, 12, planning_objects=[item])
    image = QImage(900, 600, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    metrics = render_project(
        painter, QRectF(image.rect()), project,
        PrintOptions(show_grid=False, show_title=False, show_dimensions=False),
    )
    painter.end()
    center = QPoint(
        round(metrics.layout_rect.left() + item.center.x * metrics.units_per_metre),
        round(metrics.layout_rect.top()
              + (project.hall_width - item.center.y) * metrics.units_per_metre),
    )
    assert image.pixelColor(center).green() > image.pixelColor(center).red()
    assert image.pixelColor(center) != QColor("#ffb020")


def test_marker_actions_and_translations_are_exposed():
    window = MainWindow()
    assert window.start_finish_action.text() == "Start-/Ziellinie"
    assert window.timing_loop_action.text() == "Zählschleife"
    assert TranslationManager("en").tr("Timing loop") == "Timing loop"
    assert TranslationManager("de").tr("Lock") == "Fixieren"
    assert window.measure_palette_button.defaultAction() is window.measure_action
    assert window.edit_menu.actions().index(window.start_finish_action) >= 0
    assert window.edit_menu.actions().index(window.timing_loop_action) >= 0
    assert window.feedback_action in window.help_menu.actions()
    assert window.feedback_action.text() == "Feedback: rctrackdesigner@web.de"
    window.close()


def test_fixing_marker_and_clicking_empty_space_clear_selection():
    canvas = _canvas()
    item = PlanningObject("start_finish", Point(10, 8), length=2)
    canvas.project.planning_objects.append(item)
    QTest.mouseClick(
        canvas, Qt.MouseButton.LeftButton,
        pos=canvas.world_to_screen(item.center).toPoint(),
    )
    assert canvas.selected_planning is item
    canvas.toggle_selected_planning_lock()
    assert item.locked
    assert canvas.selected_planning is None

    item.locked = False
    QTest.mouseClick(
        canvas, Qt.MouseButton.LeftButton,
        pos=canvas.world_to_screen(item.center).toPoint(),
    )
    QTest.mouseClick(
        canvas, Qt.MouseButton.LeftButton,
        pos=canvas.world_to_screen(Point(20, 15)).toPoint(),
    )
    assert canvas.selected_planning is None
    canvas.close()


def test_start_finish_line_is_perpendicular_to_straight_track_on_first_click():
    canvas = _canvas()
    straight = TrackElement(
        "straight", Point(5, 8), heading_deg=30, length=12, width=2,
    )
    canvas.project.elements.append(straight)
    first = straight.centerline_midpoint
    canvas.set_planning_placement("start_finish", 2)
    QTest.mouseClick(
        canvas, Qt.MouseButton.LeftButton,
        pos=canvas.world_to_screen(first).toPoint(),
    )
    assert canvas.planning_draft_axis_deg == pytest.approx(120)

    # Once the pointer is within five degrees of perpendicular, the live
    # endpoint must settle exactly onto that axis.
    pointer_angle = radians(117)
    pointer = Point(first.x + 3 * cos(pointer_angle),
                    first.y + 3 * sin(pointer_angle))
    QTest.mouseMove(canvas, canvas.world_to_screen(pointer).toPoint())
    preview = canvas.planning_draft_preview
    angle = radians(straight.heading_deg)
    along_track = ((preview.x - canvas.planning_draft_start.x) * cos(angle)
                   + (preview.y - canvas.planning_draft_start.y) * sin(angle))
    assert along_track == pytest.approx(0, abs=1e-9)

    QTest.mouseClick(
        canvas, Qt.MouseButton.LeftButton,
        pos=canvas.world_to_screen(pointer).toPoint(),
    )
    item = canvas.project.planning_objects[0]
    assert abs(sin(radians(item.heading_deg - straight.heading_deg))) < 1e-9
    canvas.close()


def test_timing_loop_and_free_start_finish_line_remain_freely_orientable():
    for kind in ("timing_loop", "start_finish"):
        canvas = _canvas()
        canvas.set_planning_placement(kind, 2)
        QTest.mouseClick(
            canvas, Qt.MouseButton.LeftButton,
            pos=canvas.world_to_screen(Point(15, 10)).toPoint(),
        )
        assert canvas.planning_draft_axis_deg is None
        canvas.close()


def test_unlocked_marker_snaps_perpendicular_and_slides_along_straight():
    canvas = _canvas()
    straight = TrackElement(
        "straight", Point(4, 8), heading_deg=0, length=18, width=2,
    )
    marker = PlanningObject(
        "start_finish", Point(8, 8), length=2, heading_deg=0,
    )
    canvas.project.elements.append(straight)
    canvas.project.planning_objects.append(marker)

    start = canvas.world_to_screen(marker.center).toPoint()
    target = canvas.world_to_screen(Point(14, 8.4)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, target)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)

    moved = canvas.project.planning_objects[0]
    assert moved.center.x == pytest.approx(14, abs=1 / canvas.scale)
    assert moved.center.y == pytest.approx(8)
    assert moved.heading_deg == pytest.approx(straight.heading_deg)
    canvas.close()


def test_diagonal_marker_is_not_forced_perpendicular_when_below_85_degrees():
    canvas = _canvas()
    canvas.project.elements.append(TrackElement(
        "straight", Point(4, 8), heading_deg=0, length=18, width=2,
    ))
    marker = PlanningObject(
        "start_finish", Point(8, 8), length=2, heading_deg=30,
    )
    canvas.project.planning_objects.append(marker)
    start = canvas.world_to_screen(marker.center).toPoint()
    target = canvas.world_to_screen(Point(14, 8.2)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, target)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)
    moved = canvas.project.planning_objects[0]
    assert moved.heading_deg == pytest.approx(30)
    assert moved.center.y == pytest.approx(8.2, abs=1 / canvas.scale)
    canvas.close()


def test_marker_endpoint_can_be_dragged_and_snaps_to_geometry_point():
    canvas = _canvas()
    straight = TrackElement(
        "straight", Point(4, 8), heading_deg=0, length=18, width=2,
    )
    marker = PlanningObject(
        "start_finish", Point(8, 12), length=2, heading_deg=0,
    )
    canvas.project.elements.append(straight)
    canvas.project.planning_objects.append(marker)
    moving_endpoint = canvas.world_to_screen(marker.endpoints[0]).toPoint()
    target_world = straight.start_pose.point
    target = canvas.world_to_screen(target_world).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=moving_endpoint)
    QTest.mouseMove(canvas, target)
    assert hypot(canvas.planning_snap_preview.x - target_world.x,
                 canvas.planning_snap_preview.y - target_world.y) < 1 / canvas.scale
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)
    assert canvas.planning_snap_preview is None
    endpoints = canvas.project.planning_objects[0].endpoints
    assert min(hypot(point.x - target_world.x, point.y - target_world.y)
               for point in endpoints) < 1 / canvas.scale
    canvas.close()


def test_marker_draft_shows_and_clears_snap_ring_at_magnet_point():
    canvas = _canvas("indoor")
    straight = TrackElement(
        "straight", Point(4, 8), heading_deg=0, length=12, width=0.1,
        element_type="boundary", magnet_points={"middle": 0.5},
    )
    canvas.project.elements.append(straight)
    canvas.set_planning_placement("timing_loop", 2)
    QTest.mouseClick(
        canvas, Qt.MouseButton.LeftButton,
        pos=canvas.world_to_screen(Point(8, 12)).toPoint(),
    )
    magnet = straight.pose_at("magnet:middle").point
    QTest.mouseMove(canvas, canvas.world_to_screen(magnet).toPoint())
    assert hypot(canvas.planning_snap_preview.x - magnet.x,
                 canvas.planning_snap_preview.y - magnet.y) < 1 / canvas.scale
    QTest.mouseClick(
        canvas, Qt.MouseButton.LeftButton,
        pos=canvas.world_to_screen(magnet).toPoint(),
    )
    assert canvas.planning_snap_preview is None
    canvas.close()


def test_explicit_magnet_point_wins_over_closer_boundary_contour():
    canvas = _canvas("indoor")
    straight = TrackElement(
        "straight", Point(4, 8), heading_deg=0, length=12, width=0.1,
        element_type="boundary", magnet_points={"middle": 0.5},
    )
    marker = PlanningObject(
        "start_finish", Point(10, 11), length=2, heading_deg=0,
    )
    canvas.project.elements.append(straight)
    canvas.project.planning_objects.append(marker)
    magnet = straight.pose_at("magnet:middle").point

    moving_endpoint = canvas.world_to_screen(marker.endpoints[0]).toPoint()
    # The pointer is exactly on the yellow contour but still inside the
    # magnet's catch radius. The explicit point must win over the contour.
    pointer = Point(magnet.x - 0.2, magnet.y + straight.width / 2)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=moving_endpoint)
    QTest.mouseMove(canvas, canvas.world_to_screen(pointer).toPoint())
    assert canvas.planning_snap_preview == magnet
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton,
                       pos=canvas.world_to_screen(pointer).toPoint())
    assert min(hypot(point.x - magnet.x, point.y - magnet.y)
               for point in canvas.project.planning_objects[0].endpoints) < 1e-9
    canvas.close()


def test_planning_draft_only_aligns_perpendicular_from_85_degrees():
    canvas = _canvas()
    canvas.project.elements.append(TrackElement(
        "straight", Point(4, 8), heading_deg=0, length=18, width=2,
    ))
    canvas.set_planning_placement("start_finish", 2)
    first = Point(8, 8)
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton,
                     pos=canvas.world_to_screen(first).toPoint())
    assert canvas.planning_draft_axis_deg == pytest.approx(90)

    diagonal = Point(10, 10)
    QTest.mouseMove(canvas, canvas.world_to_screen(diagonal).toPoint())
    assert canvas.planning_draft_preview.x != pytest.approx(first.x)

    nearly_perpendicular = Point(8.15, 11)
    QTest.mouseMove(canvas, canvas.world_to_screen(nearly_perpendicular).toPoint())
    assert canvas.planning_draft_preview.x == pytest.approx(
        canvas.planning_draft_start.x
    )
    canvas.close()


def test_marker_can_be_pulled_out_of_straight_snap_range():
    canvas = _canvas()
    canvas.project.elements.append(TrackElement(
        "straight", Point(4, 8), heading_deg=0, length=18, width=2,
    ))
    marker = PlanningObject("start_finish", Point(8, 8), length=2)
    canvas.project.planning_objects.append(marker)
    start = canvas.world_to_screen(marker.center).toPoint()
    target = canvas.world_to_screen(Point(14, 13)).toPoint()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, target)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)
    assert canvas.project.planning_objects[0].center.y == pytest.approx(
        13, abs=1 / canvas.scale
    )
    canvas.close()


def test_selected_marker_exposes_two_endpoint_handles():
    item = PlanningObject("timing_loop", Point(10, 8), length=3, heading_deg=30)
    first, second = item.endpoints
    assert hypot(first.x - second.x, first.y - second.y) == pytest.approx(3)
    midpoint = Point((first.x + second.x) / 2, (first.y + second.y) / 2)
    assert midpoint == item.center


def test_default_marker_length_uses_track_width_or_two_metres_indoor():
    window = MainWindow()
    window.canvas.set_project(TrackProject(editor_mode="normal"))
    window._apply_mode_ui()
    window.canvas.default_width = 3.25
    window.start_finish_action.trigger()
    assert window.canvas.planning_placement == ("start_finish", 3.25)
    window.canvas.cancel_planning_placement()
    window.canvas.set_project(TrackProject(25, 12, editor_mode="indoor"))
    window.timing_loop_action.trigger()
    assert window.canvas.planning_placement == ("timing_loop", 2.0)
    window.close()


def test_pdf_export_with_both_marker_types_is_nonempty(tmp_path):
    project = TrackProject(20, 12, planning_objects=[
        PlanningObject("start_finish", Point(6, 5), length=2),
        PlanningObject("timing_loop", Point(12, 7), length=2),
    ])
    path = tmp_path / "markers.pdf"
    options = PrintOptions()
    render_project_to_printer(pdf_printer(path, options), project, options)
    assert path.read_bytes().startswith(b"%PDF")
    assert path.stat().st_size > 1000
