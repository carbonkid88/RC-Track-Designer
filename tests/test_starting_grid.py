import os
from math import hypot

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rc_track_designer.canvas import TrackCanvas
from rc_track_designer.i18n import TranslationManager
from rc_track_designer.model import PlanningObject, Point, TrackProject
from rc_track_designer.planning import (
    draw_planning_object, planning_hit_test, starting_grid_font_size,
)
from rc_track_designer.printing import PrintOptions, pdf_printer, render_project_to_printer
from rc_track_designer.storage import load_project, save_project
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
def test_ten_starting_grid_positions_are_placed_and_numbered(mode):
    canvas = _canvas(mode)
    for index in range(10):
        canvas.set_planning_placement("starting_grid", 0.5)
        QTest.mouseClick(
            canvas, Qt.MouseButton.LeftButton,
            pos=canvas.world_to_screen(Point(3 + index * 2, 8)).toPoint(),
        )
    grids = canvas.project.planning_objects
    assert len(grids) == 10
    assert [canvas.project.starting_grid_number(item) for item in grids] == list(range(1, 11))
    assert all(item.length == pytest.approx(0.5) for item in grids)
    assert all(item.width == pytest.approx(0.2) for item in grids)
    canvas.close()


def test_move_rotate_lock_delete_and_undo_redo_keep_numbering_consistent():
    canvas = _canvas()
    grids = [PlanningObject("starting_grid", Point(5 + i * 2, 8), 0.5, 0.2)
             for i in range(3)]
    canvas.project.planning_objects.extend(grids)

    center = canvas.world_to_screen(grids[1].center).toPoint()
    target = center + QPoint(42, -21)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=center)
    QTest.mouseMove(canvas, target)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)
    moved_center = canvas.selected_planning.center
    canvas.rotate_selected(5)
    assert canvas.selected_planning.heading_deg == pytest.approx(5)
    assert canvas.project.starting_grid_number(canvas.selected_planning) == 2

    canvas.toggle_selected_planning_lock()
    locked = canvas.project.planning_objects[1]
    assert locked.locked
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton,
                     pos=canvas.world_to_screen(locked.center).toPoint())
    canvas.rotate_selected(5)
    assert locked.heading_deg == pytest.approx(5)
    canvas.toggle_selected_planning_lock()
    assert not canvas.selected_planning.locked

    canvas.delete_selected()
    assert [canvas.project.starting_grid_number(item)
            for item in canvas.project.planning_objects] == [1, 2]
    canvas.undo_stack.undo()
    assert [canvas.project.starting_grid_number(item)
            for item in canvas.project.planning_objects] == [1, 2, 3]
    assert canvas.project.planning_objects[1].center == moved_center
    canvas.undo_stack.redo()
    assert len(canvas.project.planning_objects) == 2
    canvas.close()


def test_add_move_and_rotate_each_have_undo_redo_history():
    canvas = _canvas()
    canvas.set_planning_placement("starting_grid", 0.5)
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton,
                     pos=canvas.world_to_screen(Point(8, 8)).toPoint())
    assert len(canvas.project.planning_objects) == 1
    canvas.undo_stack.undo()
    assert not canvas.project.planning_objects
    canvas.undo_stack.redo()
    item = canvas.project.planning_objects[0]

    start_center = item.center
    start = canvas.world_to_screen(item.center).toPoint()
    target = start + QPoint(42, -21)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, target)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)
    moved_center = canvas.project.planning_objects[0].center
    assert moved_center != start_center
    canvas.undo_stack.undo()
    assert canvas.project.planning_objects[0].center == start_center
    canvas.undo_stack.redo()
    assert canvas.project.planning_objects[0].center == moved_center

    canvas.rotate_selected(5)
    assert canvas.project.planning_objects[0].heading_deg == pytest.approx(5)
    canvas.undo_stack.undo()
    assert canvas.project.planning_objects[0].heading_deg == pytest.approx(0)
    canvas.undo_stack.redo()
    assert canvas.project.planning_objects[0].heading_deg == pytest.approx(5)
    canvas.close()


def test_starting_grid_roundtrip_preserves_order_identity_pose_and_lock(tmp_path):
    project = TrackProject(planning_objects=[
        PlanningObject("starting_grid", Point(4, 5), 0.5, 0.2,
                       heading_deg=15, locked=True),
        PlanningObject("start_finish", Point(8, 7)),
        PlanningObject("starting_grid", Point(12, 5), 0.5, 0.2,
                       heading_deg=35),
    ])
    path = tmp_path / "grid.rct.json"
    save_project(project, path)
    loaded = load_project(path)
    grids = [item for item in loaded.planning_objects if item.kind == "starting_grid"]
    assert [loaded.starting_grid_number(item) for item in grids] == [1, 2]
    assert [item.id for item in grids] == [project.planning_objects[0].id,
                                          project.planning_objects[2].id]
    assert grids[0].locked and grids[0].heading_deg == pytest.approx(15)


@pytest.mark.parametrize("scale", [15.0, 60.0, 180.0])
def test_starting_grid_vector_geometry_is_visible_and_hittable_at_zoom(scale):
    item = PlanningObject("starting_grid", Point(0, 0), 0.5, 0.2,
                          heading_deg=25)
    image = QImage(400, 300, QImage.Format.Format_ARGB32)
    image.fill(QColor("#555555"))
    mapper = lambda point: QPoint(200 + round(point.x * scale),
                                  150 - round(point.y * scale))
    painter = QPainter(image)
    draw_planning_object(painter, item, mapper, scale, number=7)
    painter.end()
    colors = {image.pixelColor(x, y).name()
              for x in range(image.width()) for y in range(image.height())}
    assert "#ffffff" in colors
    assert planning_hit_test(item, mapper(item.center), mapper)


def test_starting_grid_number_has_readable_minimum_size_when_zoomed_out():
    assert starting_grid_font_size(5) == 14
    assert starting_grid_font_size(25) == 14
    assert starting_grid_font_size(100) == 18


def test_starting_grid_is_rendered_to_pdf(tmp_path):
    project = TrackProject(planning_objects=[
        PlanningObject("starting_grid", Point(8, 6), 0.5, 0.2,
                       heading_deg=90),
    ])
    path = tmp_path / "starting-grid.pdf"
    options = PrintOptions(show_grid=False)
    render_project_to_printer(pdf_printer(path, options), project, options)
    assert path.read_bytes().startswith(b"%PDF")
    assert path.stat().st_size > 1000


def test_starting_grid_action_translations_and_read_only_dimensions():
    window = MainWindow()
    assert window.starting_grid_action.text() == "Startplatz hinzufügen"
    assert TranslationManager("en").tr("Starting grid position") == "Starting grid position"
    item = PlanningObject("starting_grid", Point(8, 7), 0.5, 0.2)
    window.canvas.project.planning_objects.append(item)
    window.canvas.selected_planning = item
    window._selection_changed(item)
    assert window.element_type_value.text() == "Startplatz"
    assert window.property_spins["x"].isEnabled()
    assert window.property_spins["heading_deg"].isEnabled()
    assert not window.property_spins["length"].isEnabled()
    assert not window.property_spins["width"].isEnabled()
    window.dirty = False
    window.close()
