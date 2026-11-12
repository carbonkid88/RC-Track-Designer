import os
from copy import deepcopy
from math import cos, hypot, radians, sin

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rc_track_designer.canvas import TrackCanvas
from rc_track_designer.i18n import TranslationManager
from rc_track_designer.measuring import MeasurementState, nearest_geometry_snap
from rc_track_designer.model import Point, TrackElement, TrackProject
from rc_track_designer.printing import PrintOptions, render_project
from rc_track_designer.ui import MainWindow


@pytest.fixture(scope="module", autouse=True)
def application():
    yield QApplication.instance() or QApplication([])


def _canvas(project=None):
    canvas = TrackCanvas()
    canvas.resize(900, 650)
    if project is not None:
        canvas.set_project(project)
    canvas.show()
    QApplication.processEvents()
    return canvas


def test_measurement_state_uses_unrounded_euclidean_metres():
    state = MeasurementState(active=True, start=Point(1, 2), end=Point(4, 6))
    assert state.distance == 5.0


def test_nearest_snap_uses_connector_when_it_is_actually_closest():
    element = TrackElement("straight", Point(2, 3), length=5, width=0.1,
                           element_type="boundary")
    snap = nearest_geometry_snap(
        TrackProject(elements=[element], editor_mode="indoor"),
        Point(1.98, 3.0),
        0.2,
    )
    assert snap is not None
    assert snap.point == element.start
    assert snap.source == "connector"


def test_nearest_snap_finds_straight_boundary_contour_not_centerline():
    boundary = TrackElement("straight", Point(2, 5), length=8, width=0.1,
                            element_type="boundary")
    snap = nearest_geometry_snap(
        TrackProject(elements=[boundary], editor_mode="indoor"),
        Point(6, 5.08),
        0.1,
    )
    assert snap is not None
    assert snap.source == "contour"
    assert snap.point.x == pytest.approx(6)
    assert snap.point.y == pytest.approx(5.05)


def test_nearest_snap_finds_curved_boundary_outer_contour():
    boundary = TrackElement("left", Point(5, 5), radius=2, angle_deg=90,
                            width=0.2, element_type="boundary")
    center = Point(5, 7)
    angle = radians(-45)
    expected = Point(center.x + 2.1 * cos(angle), center.y + 2.1 * sin(angle))
    query = Point(center.x + 2.14 * cos(angle), center.y + 2.14 * sin(angle))
    snap = nearest_geometry_snap(
        TrackProject(elements=[boundary], editor_mode="indoor"), query, 0.1
    )
    assert snap is not None
    assert snap.source == "contour"
    assert hypot(snap.point.x - expected.x, snap.point.y - expected.y) < 1e-8


def test_two_clicks_measure_freely_without_project_or_undo_changes():
    canvas = _canvas()
    before = deepcopy(canvas.project)
    undo_count = canvas.undo_stack.count()
    canvas.set_measurement_mode(True)
    first = canvas.world_to_screen(Point(3, 4)).toPoint()
    second = canvas.world_to_screen(Point(6, 8)).toPoint()

    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseMove(canvas, second)
    assert canvas.measurement.preview is not None
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=second)

    assert canvas.measurement.distance == pytest.approx(5.0, abs=0.03)
    assert canvas.project == before
    assert canvas.undo_stack.count() == undo_count
    canvas.close()


def test_measurement_clicks_do_not_select_or_move_elements():
    element = TrackElement("straight", Point(3, 5), length=8)
    canvas = _canvas(TrackProject(elements=[element]))
    canvas.set_measurement_mode(True)
    before = deepcopy(canvas.project)
    QTest.mouseClick(
        canvas, Qt.MouseButton.LeftButton,
        pos=canvas.world_to_screen(Point(6, 5)).toPoint(),
    )
    assert canvas.selected is None
    assert canvas.project == before
    canvas.close()


def test_measurement_hover_highlights_snap_before_first_click_and_blocks_placement():
    boundary = TrackElement("straight", Point(2, 5), length=8, width=0.1,
                            element_type="boundary")
    canvas = _canvas(TrackProject(elements=[boundary], editor_mode="indoor"))
    canvas.set_measurement_mode(True)
    edge = canvas.world_to_screen(Point(6, 5.05)).toPoint()
    QTest.mouseMove(canvas, edge)
    assert canvas.measurement.snap_point is not None
    canvas.set_placement("straight")
    assert canvas.placement is None
    canvas.close()


def test_snap_distance_stays_screen_based_across_zoom_levels():
    boundary = TrackElement("straight", Point(2, 5), length=8, width=0.1,
                            element_type="boundary")
    canvas = _canvas(TrackProject(elements=[boundary], editor_mode="indoor"))
    canvas.set_measurement_mode(True)
    for scale in (10.0, 100.0):
        canvas.scale = scale
        edge = canvas.world_to_screen(Point(6, 5.05))
        snapped = canvas._measurement_point(edge + QPointF(0, -10))
        assert snapped.y == pytest.approx(5.05)
    canvas.close()


def test_middle_mouse_pan_and_wheel_zoom_remain_available_while_measuring():
    canvas = _canvas()
    canvas.set_measurement_mode(True)
    original_pan = QPointF(canvas.pan)
    QTest.mousePress(canvas, Qt.MouseButton.MiddleButton, pos=QPoint(250, 250))
    QTest.mouseMove(canvas, QPoint(275, 270))
    QTest.mouseRelease(canvas, Qt.MouseButton.MiddleButton, pos=QPoint(275, 270))
    assert canvas.pan != original_pan
    assert canvas.measurement.start is None
    canvas.close()


def test_clear_and_exit_remove_complete_or_incomplete_measurement():
    canvas = _canvas()
    canvas.set_measurement_mode(True)
    canvas.measurement.start = Point(1, 1)
    canvas.clear_measurement()
    assert canvas.measurement.active
    assert canvas.measurement.start is None
    canvas.measurement.start = Point(2, 2)
    canvas.measurement.end = Point(3, 3)
    canvas.exit_measurement()
    assert not canvas.measurement.active
    assert canvas.measurement.start is None
    assert canvas.measurement.end is None
    canvas.close()


def test_context_menu_clear_and_exit_actions():
    canvas = _canvas()
    canvas.set_measurement_mode(True)
    canvas.measurement.start = Point(1, 1)
    menu = canvas._build_measurement_context_menu()
    assert [action.text() for action in menu.actions()] == [
        "Clear measurement", "Exit measurement"
    ]
    menu.actions()[0].trigger()
    assert canvas.measurement.active and canvas.measurement.start is None

    canvas.measurement.start = Point(1, 1)
    menu.actions()[1].trigger()
    assert not canvas.measurement.active
    canvas.close()


def test_project_change_discards_measurement_but_keeps_tool_active():
    canvas = _canvas()
    canvas.set_measurement_mode(True)
    canvas.measurement.start = Point(4, 4)
    canvas.measurement.end = Point(6, 6)
    canvas.set_project(TrackProject(25, 12, editor_mode="indoor"))
    assert canvas.measurement.active
    assert canvas.measurement.start is None
    assert canvas.project.editor_mode == "indoor"
    canvas.close()


def test_measurement_overlay_is_not_part_of_print_renderer():
    project = TrackProject(elements=[
        TrackElement("straight", Point(3, 5), length=8, width=2)
    ])
    canvas = _canvas(project)

    def printed_image():
        image = QImage(800, 500, QImage.Format.Format_ARGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        render_project(
            painter, QRectF(image.rect()), canvas.project,
            PrintOptions(show_title=False, show_dimensions=False),
        )
        painter.end()
        return image

    before = printed_image()
    canvas.set_measurement_mode(True)
    canvas.measurement.start = Point(2, 2)
    canvas.measurement.end = Point(9, 8)
    after = printed_image()
    assert before == after
    canvas.close()


def test_measure_action_and_translations_are_available_in_both_languages():
    window = MainWindow()
    assert window.measure_action in window.edit_menu.actions()
    window.measure_action.trigger()
    assert window.canvas.measurement.active
    window.measure_action.trigger()
    assert not window.canvas.measurement.active
    assert TranslationManager("de").tr("Measure") == "Maßband"
    assert TranslationManager("de").tr("Clear measurement") == "Messung auflösen"
    assert TranslationManager("en").tr("Measure") == "Measure"
    window.close()
