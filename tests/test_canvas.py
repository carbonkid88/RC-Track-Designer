import os
from math import isclose

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rc_track_designer.canvas import TrackCanvas
from rc_track_designer.model import Point, TrackElement


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
