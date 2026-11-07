"""Qt-Zeichenfläche für Darstellung und direkte Bearbeitung."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFocusEvent, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPainterPathStroker, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from .model import Point, TrackElement, TrackProject


class TrackCanvas(QWidget):
    project_changed = Signal()
    selection_changed = Signal(object)
    status_message = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.project = TrackProject()
        self.scale = 25.0
        self.pan = QPointF(35.0, 35.0)
        self.selected: TrackElement | None = None
        self.placement: tuple[str, float] | None = None
        self.default_width = 2.0
        self.default_length = 5.0
        self.default_radius = 5.0
        self._last_mouse = QPoint()
        self._dragging_element = False
        self._panning = False
        self._space_pressed = False
        self._view_fitted = True
        self._colors = {
            "canvas": "#202326", "hall": "#e8e8e4", "grid": "#c9c9c4",
            "track": "#555b62", "centerline": "#f7f7f7", "text": "#f3f5f7",
        }
        self._tr = lambda text, **values: text.format(**values) if values else text
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(640, 400)

    def set_project(self, project: TrackProject) -> None:
        self.project = project
        self.selected = None
        self.placement = None
        self.fit_to_view()
        self.selection_changed.emit(None)
        self.update()

    def fit_to_view(self) -> None:
        margin = 50.0
        if self.width() > 100 and self.height() > 100:
            self.scale = max(2.0, min((self.width() - 2 * margin) / self.project.hall_length,
                                      (self.height() - 2 * margin) / self.project.hall_width))
        hall_pixels_w = self.project.hall_length * self.scale
        hall_pixels_h = self.project.hall_width * self.scale
        self.pan = QPointF((self.width() - hall_pixels_w) / 2,
                           (self.height() - hall_pixels_h) / 2)
        self._view_fitted = True
        self.update()

    def set_appearance(self, colors: dict[str, str], translator=None) -> None:
        self._colors.update(colors)
        if translator:
            self._tr = translator
        self.update()

    def world_to_screen(self, p: Point) -> QPointF:
        return QPointF(self.pan.x() + p.x * self.scale,
                       self.pan.y() + (self.project.hall_width - p.y) * self.scale)

    def screen_to_world(self, p: QPointF) -> Point:
        return Point((p.x() - self.pan.x()) / self.scale,
                     self.project.hall_width - (p.y() - self.pan.y()) / self.scale)

    def set_placement(self, kind: str, angle: float = 0.0) -> None:
        self.placement = (kind, angle)
        self.setCursor(Qt.CursorShape.CrossCursor)
        if kind == "straight":
            label = self._tr("straight")
        else:
            label = self._tr("left curve {angle}°" if kind == "left" else "right curve {angle}°", angle=f"{angle:g}")
        self.status_message.emit(self._tr("Click inside the hall to place {element}; Esc cancels.", element=label))
        self.update()

    def cancel_placement(self) -> None:
        self.placement = None
        self.unsetCursor()
        self.status_message.emit(self._tr("Selection mode"))
        self.update()

    def rotate_selected(self, degrees: float) -> None:
        if self.selected:
            self.selected.rotate(degrees)
            self.project_changed.emit()
            self.update()

    def delete_selected(self) -> None:
        if self.selected and self.selected in self.project.elements:
            self.project.elements.remove(self.selected)
            self.selected = None
            self.selection_changed.emit(None)
            self.project_changed.emit()
            self.update()

    def _element_path(self, element: TrackElement) -> QPainterPath:
        points = element.centerline_points()
        path = QPainterPath(self.world_to_screen(points[0]))
        for point in points[1:]:
            path.lineTo(self.world_to_screen(point))
        return path

    def _hit_test(self, pos: QPointF) -> TrackElement | None:
        for element in reversed(self.project.elements):
            stroker = QPainterPathStroker()
            stroker.setWidth(max(10.0, element.width * self.scale + 8.0))
            if stroker.createStroke(self._element_path(element)).contains(pos):
                return element
        return None

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self._colors["canvas"]))
        hall = QRectF(self.pan.x(), self.pan.y(), self.project.hall_length * self.scale,
                      self.project.hall_width * self.scale)
        painter.fillRect(hall, QColor(self._colors["hall"]))
        painter.save()
        painter.setClipRect(hall)
        grid = 1 if self.scale >= 12 else 5
        painter.setPen(QPen(QColor(self._colors["grid"]), 1))
        x = 0
        while x <= self.project.hall_length:
            sx = self.world_to_screen(Point(x, 0)).x()
            painter.drawLine(QPointF(sx, hall.top()), QPointF(sx, hall.bottom()))
            x += grid
        y = 0
        while y <= self.project.hall_width:
            sy = self.world_to_screen(Point(0, y)).y()
            painter.drawLine(QPointF(hall.left(), sy), QPointF(hall.right(), sy))
            y += grid
        for element in self.project.elements:
            path = self._element_path(element)
            if element is self.selected:
                painter.setPen(QPen(QColor("#ffb020"), element.width * self.scale + 8,
                                    Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.RoundJoin))
                painter.drawPath(path)
            painter.setPen(QPen(QColor(self._colors["track"]), element.width * self.scale,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(path)
            painter.setPen(QPen(QColor(self._colors["centerline"]), 1, Qt.PenStyle.DashLine))
            painter.drawPath(path)
            for pose in (element.start_pose, element.end_pose):
                point = self.world_to_screen(pose.point)
                painter.setBrush(QColor("#31a8ff"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(point, 3.5, 3.5)
        painter.restore()
        painter.setPen(QPen(QColor("#111111"), 2))
        painter.drawRect(hall)
        painter.setPen(QColor(self._colors["text"]))
        painter.drawText(QPointF(hall.left(), max(16, hall.top() - 9)),
                         f"{self.project.hall_length:g} m × {self.project.hall_width:g} m  |  {self._tr('Grid {grid} m', grid=grid)}")

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        before = self.screen_to_world(event.position())
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale = min(250.0, max(2.0, self.scale * factor))
        after_screen = self.world_to_screen(before)
        self.pan += event.position() - after_screen
        self._view_fitted = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.setFocus()
        self._last_mouse = event.position().toPoint()
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and self._space_pressed):
            self._panning = True
            self._view_fitted = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        world = self.screen_to_world(event.position())
        if self.placement:
            kind, angle = self.placement
            if 0 <= world.x <= self.project.hall_length and 0 <= world.y <= self.project.hall_width:
                element = TrackElement(kind, world, width=self.default_width, length=self.default_length,
                                       radius=self.default_radius, angle_deg=angle or 45.0)
                self.project.elements.append(element)
                self.selected = element
                self.selection_changed.emit(element)
                self.project_changed.emit()
                self.update()
            return
        self.selected = self._hit_test(event.position())
        self._dragging_element = self.selected is not None
        self.selection_changed.emit(self.selected)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        delta = event.position().toPoint() - self._last_mouse
        self._last_mouse = event.position().toPoint()
        if self._panning:
            self.pan += QPointF(delta)
            self.update()
        elif self._dragging_element and self.selected:
            self.selected.moved(delta.x() / self.scale, -delta.y() / self.scale)
            self.project_changed.emit()
            self.update()
        else:
            w = self.screen_to_world(event.position())
            self.status_message.emit(f"x {w.x:.2f} m · y {w.y:.2f} m")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._panning = False
        self._dragging_element = False
        self.unsetCursor()
        if self.placement:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space:
            self._space_pressed = True
            if not self._panning:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.cancel_placement()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        elif event.key() == Qt.Key.Key_R:
            self.rotate_selected(-5 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 5)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space:
            self._space_pressed = False
            if not self._panning:
                self.unsetCursor()
                if self.placement:
                    self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        # Verhindert einen hängenbleibenden Pan-Modus, wenn Alt+Tab oder ein
        # anderes Fenster den KeyRelease-/MouseRelease-Event übernimmt.
        self._space_pressed = False
        self._panning = False
        self._dragging_element = False
        self.unsetCursor()
        if self.placement:
            self.setCursor(Qt.CursorShape.CrossCursor)
        super().focusOutEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._view_fitted:
            self.fit_to_view()
