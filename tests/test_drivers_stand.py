import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rc_track_designer.canvas import TrackCanvas
from rc_track_designer.i18n import TranslationManager
from rc_track_designer.model import PlanningObject, Point, TrackProject
from rc_track_designer.planning import drivers_stand_handles, planning_hit_test
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
def test_place_default_drivers_stand_in_both_modes(mode):
    canvas = _canvas(mode)
    canvas.set_planning_placement("drivers_stand", 4.0)
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton,
                     pos=canvas.world_to_screen(Point(10, 8)).toPoint())
    item = canvas.project.planning_objects[0]
    assert item.kind == "drivers_stand"
    assert item.length == pytest.approx(4.0)
    assert item.width == pytest.approx(1.0)
    assert item.heading_deg == pytest.approx(0.0)
    canvas.close()


def test_numeric_edit_rotate_lock_and_roundtrip(tmp_path):
    canvas = _canvas()
    item = PlanningObject("drivers_stand", Point(10, 8), 4, 1)
    canvas.project.planning_objects.append(item)
    canvas.selected_planning = item
    canvas.change_selected("edit", length=5.25, width=1.4, heading_deg=25)
    assert (item.length, item.width, item.heading_deg) == pytest.approx((5.25, 1.4, 25))
    canvas.toggle_selected_planning_lock()
    assert item.locked and canvas.selected_planning is item
    canvas.change_selected("blocked", length=8)
    assert item.length == pytest.approx(5.25)
    path = tmp_path / "stand.rct.json"
    save_project(canvas.project, path)
    loaded = load_project(path).planning_objects[0]
    assert loaded.id == item.id
    assert (loaded.length, loaded.width, loaded.heading_deg) == pytest.approx((5.25, 1.4, 25))
    assert loaded.locked
    canvas.close()


@pytest.mark.parametrize("handle, dimension", [
    ("left", "length"), ("right", "length"),
    ("top", "width"), ("bottom", "width"),
])
def test_each_side_handle_resizes_rotated_stand_with_opposite_side_fixed(handle, dimension):
    canvas = _canvas()
    item = PlanningObject("drivers_stand", Point(12, 9), 4, 1, heading_deg=30)
    canvas.project.planning_objects.append(item)
    canvas.selected_planning = item
    before = drivers_stand_handles(item)
    opposite = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}[handle]
    start = canvas.world_to_screen(before[handle]).toPoint()
    center = canvas.world_to_screen(item.center).toPoint()
    delta = start - center
    target = start + QPoint(round(delta.x() * 0.25), round(delta.y() * 0.25))
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, target)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=target)
    after = drivers_stand_handles(item)
    assert getattr(item, dimension) > (4 if dimension == "length" else 1)
    assert after[opposite].x == pytest.approx(before[opposite].x, abs=0.03)
    assert after[opposite].y == pytest.approx(before[opposite].y, abs=0.03)
    canvas.undo_stack.undo()
    restored = canvas.project.planning_objects[0]
    assert (restored.length, restored.width) == pytest.approx((4, 1))
    canvas.close()


def test_drivers_stand_hit_test_and_pdf(tmp_path):
    project = TrackProject(planning_objects=[
        PlanningObject("drivers_stand", Point(8, 6), 4, 1, heading_deg=15),
    ])
    item = project.planning_objects[0]
    mapper = lambda point: QPoint(round(point.x * 30), round(point.y * 30))
    assert planning_hit_test(item, mapper(item.center), mapper)
    path = tmp_path / "drivers-stand.pdf"
    options = PrintOptions(show_grid=False)
    render_project_to_printer(pdf_printer(path, options), project, options,
                              tr=TranslationManager("en").tr)
    assert path.read_bytes().startswith(b"%PDF")
    assert path.stat().st_size > 1000


def test_drivers_stand_ui_and_translations():
    window = MainWindow()
    assert window.drivers_stand_action.text() == "Fahrerstand hinzufügen"
    assert TranslationManager("en").tr("Drivers' Stand") == "Drivers' Stand"
    item = PlanningObject("drivers_stand", Point(8, 7), 4, 1)
    window.canvas.project.planning_objects.append(item)
    window.canvas.selected_planning = item
    window._selection_changed(item)
    assert window.element_type_value.text() == "Fahrerstand"
    assert window.property_spins["length"].isEnabled()
    assert window.property_spins["width"].isEnabled()
    item.locked = True
    window._sync_properties(item)
    assert not window.property_spins["length"].isEnabled()
    assert not window.property_spins["width"].isEnabled()
    window.dirty = False
    window.close()
