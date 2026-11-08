"""Qt-Zeichenfläche für Darstellung und direkte Bearbeitung."""

from __future__ import annotations

from copy import deepcopy
from math import cos, hypot, radians, sin

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QFocusEvent, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF, QUndoStack, QWheelEvent
from PySide6.QtWidgets import QMenu, QRubberBand, QWidget

from .commands import ProjectStateCommand
from .model import ConnectorRef, Point, Pose, TrackElement, TrackProject


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
        self.selected_ids: set[str] = set()
        self.placement: tuple[str, float] | None = None
        self.default_width = 2.0
        self.default_length = 5.0
        self.default_radius = 5.0
        self._last_mouse = QPoint()
        self._dragging_element = False
        self._drag_started = False
        self._drag_before = None
        self._drag_ignored_pairs: set[frozenset[str]] = set()
        self._panning = False
        self._selecting_rect = False
        self._rubber_origin = QPoint()
        self._rubber_additive = False
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._space_pressed = False
        self._view_fitted = True
        self._colors = {
            "canvas": "#202326", "hall": "#e8e8e4", "grid": "#c9c9c4",
            "track": "#555b62", "centerline": "#f7f7f7", "text": "#f3f5f7",
        }
        self._tr = lambda text, **values: text.format(**values) if values else text
        self.undo_stack = QUndoStack(self)
        self.active_connector: ConnectorRef | None = None
        self.snap_distance_px = 34.0
        self.connector_hit_distance_px = 10.0
        # A modest angular tolerance makes docking helpful without undoing a
        # deliberate manual rotation from far outside the target tangent.
        self.tangent_tolerance_deg = 30.0
        self.snap_preview: tuple[ConnectorRef, ConnectorRef] | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(640, 400)

    def set_project(self, project: TrackProject) -> None:
        self.project = project
        self.selected = None
        self.selected_ids.clear()
        self.active_connector = None
        self.placement = None
        self.undo_stack.clear()
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
        if self.active_connector and self.project.is_free(self.active_connector):
            self._append_to_active(kind, angle or 45.0)
            return
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
            target_heading = (self.selected.heading_deg + degrees) % 360
            if not self.manual_heading_allowed(self.selected, target_heading):
                self.status_message.emit(self._tr(
                    "This {curve_angle}° curve may be rotated manually by at most {rotation}°.",
                    curve_angle=f"{self.selected.angle_deg:g}",
                    rotation=f"{self.maximum_manual_rotation(self.selected):g}",
                ))
                return
            before = deepcopy(self.project)
            before_connector = self.active_connector
            before_selection = self._selection_state()
            self.project.disconnect_element(self.selected.id)
            self.selected.rotate(degrees)
            if not self.project.element_fits_hall(self.selected):
                self._restore_without_signal(before, self.selected.id, before_connector)
                self.status_message.emit(self._tr("The element would extend beyond the hall."))
                return
            if self._would_overlap(self.selected):
                self._restore_without_signal(before, before_selection, before_connector)
                self.selection_changed.emit(self.selected); self.update()
                self.status_message.emit(self._tr("Rotation would overlap another element. Disconnect and move it first."))
                return
            self.active_connector = None
            self.selected_ids = {self.selected.id}
            self._commit_change(self._tr("Rotate element"), before, before_selection, before_connector)

    @staticmethod
    def maximum_manual_rotation(element: TrackElement) -> float:
        if element.kind == "straight":
            return 360.0
        return max(0.0, 90.0 - element.angle_deg)

    @staticmethod
    def manual_heading_allowed(element: TrackElement, heading_deg: float) -> bool:
        if element.kind == "straight":
            return True
        heading = heading_deg % 360
        maximum = TrackCanvas.maximum_manual_rotation(element)
        return (0 <= heading <= maximum + 1e-9
                or heading == 0
                or 360 - maximum - 1e-9 <= heading < 360)

    def can_rotate_selected(self, degrees: float) -> bool:
        return bool(self.selected and self.manual_heading_allowed(
            self.selected, self.selected.heading_deg + degrees
        ))

    def delete_selected(self) -> None:
        if self.selected and self.selected in self.project.elements:
            before = deepcopy(self.project); before_selection = self._selection_state(); before_connector = self.active_connector
            if not self.selected_ids: self.selected_ids = {self.selected.id}
            for element in list(self.project.elements):
                if element.id in self.selected_ids: self.project.remove_element(element)
            self.selected = None
            self.selected_ids.clear()
            self.active_connector = None
            self.selection_changed.emit(None)
            self._commit_change(self._tr("Delete element"), before, before_selection, before_connector)

    def change_selected(self, text: str, **values: float) -> None:
        if not self.selected: return
        before = deepcopy(self.project); before_connector = self.active_connector; before_selection = self._selection_state()
        self.project.disconnect_element(self.selected.id)
        if "x" in values or "y" in values:
            self.selected.start = Point(values.get("x", self.selected.start.x), values.get("y", self.selected.start.y))
        for name in ("heading_deg", "width", "length", "radius", "angle_deg"):
            if name in values: setattr(self.selected, name, values[name])
        if "heading_deg" in values:
            self.selected.heading_deg %= 360
        if "heading_deg" in values or "angle_deg" in values:
            if not self.manual_heading_allowed(self.selected, self.selected.heading_deg):
                self._restore_without_signal(before, before_selection, before_connector)
                self.selection_changed.emit(self.selected); self.update()
                self.status_message.emit(self._tr(
                    "Curve angle and manual rotation may total at most 90°."
                ))
                return
        if not self.project.element_fits_hall(self.selected):
            selected_id = self.selected.id
            self._restore_without_signal(before, selected_id, before_connector)
            self.selection_changed.emit(self.selected); self.update()
            self.status_message.emit(self._tr("The element would extend beyond the hall."))
            return
        self.active_connector = None
        self.selected_ids = {self.selected.id}
        self._commit_change(text, before, before_selection, before_connector)

    def disconnect_connector(self, connector: ConnectorRef) -> bool:
        connection = self.project.connection_for(connector)
        if connection is None: return False
        before = deepcopy(self.project); before_selection = self._selection_state(); before_connector = self.active_connector
        self.project.disconnect(connector)
        self.selected = self.project.element_by_id(connector.element_id)
        self.selected_ids = {connector.element_id}
        self.active_connector = connector
        self._commit_change(self._tr("Disconnect track elements"), before, before_selection, before_connector)
        self.status_message.emit(self._tr("Connection released; the selected connector is now active."))
        return True

    def _selection_id(self) -> str | None:
        return self.selected.id if self.selected else None

    def _selection_state(self):
        ids = self.selected_ids or ({self.selected.id} if self.selected else set())
        return self._selection_id(), tuple(sorted(ids))

    def _restore_state(self, project: TrackProject, selection, connector: ConnectorRef | None) -> None:
        self._restore_without_signal(project, selection, connector)
        self.selection_changed.emit(self.selected)
        self.project_changed.emit(); self.update()

    def _restore_without_signal(self, project: TrackProject, selection,
                                connector: ConnectorRef | None) -> None:
        self.project = project
        if isinstance(selection, tuple) and len(selection) == 2 and isinstance(selection[1], tuple):
            selected_id, ids = selection
            self.selected_ids = {item for item in ids if project.element_by_id(item)}
        else:
            selected_id = selection
            self.selected_ids = {selected_id} if selected_id and project.element_by_id(selected_id) else set()
        self.selected = project.element_by_id(selected_id) if selected_id else None
        self.active_connector = connector if connector and project.is_free(connector) else None

    def _commit_change(self, text: str, before: TrackProject, before_selection,
                       before_connector: ConnectorRef | None) -> None:
        command = ProjectStateCommand(text, before, self.project, before_selection, self._selection_state(),
                                      before_connector, self.active_connector, self._restore_state)
        self.undo_stack.push(command)
        self.selection_changed.emit(self.selected)
        self.project_changed.emit(); self.update()

    @staticmethod
    def _angle_difference(first: float, second: float) -> float:
        return abs((first - second + 180) % 360 - 180)

    def _connector_at(self, pos: QPointF, free_only: bool = False) -> ConnectorRef | None:
        best = None; best_distance = self.connector_hit_distance_px
        for element in self.project.elements:
            for endpoint in ("start", "end"):
                connector = ConnectorRef(element.id, endpoint)
                if free_only and not self.project.is_free(connector): continue
                screen = self.world_to_screen(element.pose_at(endpoint).point)
                distance = hypot(screen.x() - pos.x(), screen.y() - pos.y())
                if distance <= best_distance: best, best_distance = connector, distance
        return best

    def _append_to_active(self, kind: str, angle: float) -> None:
        connector = self.active_connector
        if not connector or not self.project.is_free(connector): return
        before = deepcopy(self.project); before_connector = connector; before_selection = self._selection_state()
        target = self.project.connector_pose(connector)
        new_endpoint = "start" if connector.endpoint == "end" else "end"
        element = TrackElement(kind, target.point, width=self.default_width, length=self.default_length,
                               radius=self.default_radius, angle_deg=angle)
        element.align_endpoint(new_endpoint, target)
        if not self.project.element_fits_hall(element):
            self.status_message.emit(self._tr("The element would extend beyond the hall."))
            return
        if self._would_overlap(element, {connector.element_id}):
            self.status_message.emit(self._tr("Track elements may not overlap."))
            return
        self.project.elements.append(element)
        new_connector = ConnectorRef(element.id, new_endpoint)
        self.project.connect(connector, new_connector)
        self.selected = element; self.selected_ids = {element.id}
        self.active_connector = ConnectorRef(element.id, "end" if new_endpoint == "start" else "start")
        self._commit_change(self._tr("Add connected element"), before, before_selection, before_connector)

    def _find_snap(self, element: TrackElement):
        best = None
        for own_endpoint in ("start", "end"):
            own = ConnectorRef(element.id, own_endpoint)
            if not self.project.is_free(own): continue
            pose = element.pose_at(own_endpoint); screen = self.world_to_screen(pose.point)
            for other in self.project.elements:
                if other.id == element.id: continue
                opposite = "end" if own_endpoint == "start" else "start"
                candidate = ConnectorRef(other.id, opposite)
                if not self.project.is_free(candidate): continue
                target = other.pose_at(opposite); target_screen = self.world_to_screen(target.point)
                distance = hypot(screen.x() - target_screen.x(), screen.y() - target_screen.y())
                angle = self._angle_difference(pose.heading_deg, target.heading_deg)
                if distance <= self.snap_distance_px and angle <= self.tangent_tolerance_deg:
                    score = distance + angle
                    if best is None or score < best[0]: best = (score, own, candidate, target)
        return best

    def _snap_element(self, element: TrackElement) -> bool:
        best = self._find_snap(element)
        if not best: return False
        _, own, candidate, target = best
        element.align_endpoint(own.endpoint, target)
        self.project.connect(own, candidate)
        self.active_connector = ConnectorRef(element.id, "end" if own.endpoint == "start" else "start")
        self.status_message.emit(self._tr("Element snapped into place."))
        return True

    def _element_path(self, element: TrackElement) -> QPainterPath:
        path = QPainterPath(self.world_to_screen(element.start))
        if element.kind == "straight":
            path.lineTo(self.world_to_screen(element.end_pose.point))
            return path
        turn = 1 if element.kind == "left" else -1
        heading = radians(element.heading_deg)
        center = Point(
            element.start.x - turn * element.radius * sin(heading),
            element.start.y + turn * element.radius * cos(heading),
        )
        center_screen = self.world_to_screen(center)
        radius_px = element.radius * self.scale
        circle = QRectF(center_screen.x() - radius_px, center_screen.y() - radius_px,
                        2 * radius_px, 2 * radius_px)
        # arcTo() inserts a line when the current point differs even by a
        # fraction of a pixel from Qt's internally approximated arc start.
        # With a wide road pen that microscopic line creates a large round
        # join (the visible "nose" on rotated curves). arcMoveTo avoids it.
        path = QPainterPath()
        path.arcMoveTo(circle, element.heading_deg - turn * 90)
        path.arcTo(circle, element.heading_deg - turn * 90, element.signed_angle_deg)
        return path

    def _road_shape(self, element: TrackElement) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(max(0.1, element.width * self.scale - 0.5))
        stroker.setCapStyle(Qt.PenCapStyle.FlatCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return stroker.createStroke(self._element_path(element))

    @staticmethod
    def _shapes_overlap(first: QPainterPath, second: QPainterPath) -> bool:
        bounds = first.intersected(second).boundingRect()
        return bounds.width() * bounds.height() > 0.25

    def _would_overlap(self, element: TrackElement, ignored_ids: set[str] | None = None) -> bool:
        ignored_ids = ignored_ids or set()
        shape = self._road_shape(element)
        return any(other.id not in ignored_ids and self._shapes_overlap(shape, self._road_shape(other))
                   for other in self.project.elements if other.id != element.id)

    def _selection_collides(self, stationary_shapes=None) -> bool:
        moving = [item for item in self.project.elements if item.id in self.selected_ids]
        if stationary_shapes is None:
            stationary_shapes = [(item, self._road_shape(item)) for item in self.project.elements if item.id not in self.selected_ids]
        for first in moving:
            first_shape = self._road_shape(first)
            for second, second_shape in stationary_shapes:
                if frozenset((first.id, second.id)) in self._drag_ignored_pairs: continue
                if self._shapes_overlap(first_shape, second_shape): return True
        return False

    def _remember_initial_overlaps(self) -> None:
        """Allow an already overlapping selection to be dragged out of trouble."""
        moving = [item for item in self.project.elements if item.id in self.selected_ids]
        stationary = [item for item in self.project.elements if item.id not in self.selected_ids]
        for first in moving:
            first_shape = self._road_shape(first)
            for second in stationary:
                if self._shapes_overlap(first_shape, self._road_shape(second)):
                    self._drag_ignored_pairs.add(frozenset((first.id, second.id)))

    def _forget_resolved_overlaps(self) -> None:
        for pair in list(self._drag_ignored_pairs):
            if len(pair) != 2:
                continue
            first_id, second_id = tuple(pair)
            first = self.project.element_by_id(first_id)
            second = self.project.element_by_id(second_id)
            if first is None or second is None or not self._shapes_overlap(
                    self._road_shape(first), self._road_shape(second)):
                self._drag_ignored_pairs.remove(pair)

    def _move_selection_safely(self, dx: float, dy: float) -> tuple[float, float]:
        elements = [item for item in self.project.elements if item.id in self.selected_ids]
        stationary_shapes = [(item, self._road_shape(item)) for item in self.project.elements if item.id not in self.selected_ids]
        dx, dy = self.project.clamp_group_translation(elements, dx, dy)
        if abs(dx) <= 1e-12 and abs(dy) <= 1e-12: return 0.0, 0.0
        for item in elements: item.moved(dx, dy)
        if not self._selection_collides(stationary_shapes): return dx, dy
        for item in elements: item.moved(-dx, -dy)
        low, high = 0.0, 1.0
        for _ in range(8):
            fraction = (low + high) / 2
            for item in elements: item.moved(dx * fraction, dy * fraction)
            collision = self._selection_collides(stationary_shapes)
            for item in elements: item.moved(-dx * fraction, -dy * fraction)
            if collision: high = fraction
            else: low = fraction
        for item in elements: item.moved(dx * low, dy * low)
        return dx * low, dy * low

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
        # Draw the same filled contours that are used for hit testing and
        # collision detection. This avoids wide-pen artifacts on tight curves.
        for element in self.project.elements:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._colors["track"]))
            painter.drawPath(self._road_shape(element))
        # A very shallow tangent-aligned bridge removes antialiasing hairlines
        # without creating a round bulge on short curve segments.
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(self._colors["track"]))
        for connection in self.project.connections:
            first = self.project.element_by_id(connection.first.element_id)
            second = self.project.element_by_id(connection.second.element_id)
            pose = self.project.connector_pose(connection.first)
            point = self.world_to_screen(pose.point)
            half_width = min(first.width, second.width) * self.scale / 2
            half_depth = 1.5
            angle = radians(pose.heading_deg)
            tangent = QPointF(cos(angle), -sin(angle))
            normal = QPointF(sin(angle), cos(angle))
            polygon = QPolygonF([
                point - tangent * half_depth - normal * half_width,
                point + tangent * half_depth - normal * half_width,
                point + tangent * half_depth + normal * half_width,
                point - tangent * half_depth + normal * half_width,
            ])
            painter.drawPolygon(polygon)
        # Outline the actual road contour instead of drawing a second, wider
        # road underneath it. The old halo produced wedges and uneven caps on
        # selected 75°–90° curves.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#ffb020"), 3, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for element in self.project.elements:
            if element.id in self.selected_ids:
                painter.drawPath(self._road_shape(element))
        for element in self.project.elements:
            painter.setPen(QPen(QColor(self._colors["centerline"]), 1, Qt.PenStyle.DashLine))
            painter.drawPath(self._element_path(element))
        if self.snap_preview:
            painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QColor("#ffad24"), 3))
            for connector in self.snap_preview:
                point = self.world_to_screen(self.project.connector_pose(connector).point)
                painter.drawEllipse(point, 10, 10)
        for element in self.project.elements:
            for endpoint in ("start", "end"):
                connector = ConnectorRef(element.id, endpoint)
                point = self.world_to_screen(element.pose_at(endpoint).point)
                if connector == self.active_connector:
                    color, radius = QColor("#ffad24"), 4.5
                elif self.project.connection_for(connector):
                    color, radius = QColor("#40c463"), 3.5
                else:
                    color, radius = QColor("#31a8ff"), 3.5
                painter.setBrush(color); painter.setPen(QPen(QColor("#101214"), 1))
                painter.drawEllipse(point, radius, radius)
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
            connector = self._connector_at(event.position(), free_only=True)
            if connector:
                self.active_connector = connector
                kind, angle = self.placement
                self.placement = None; self.unsetCursor()
                self._append_to_active(kind, angle or 45.0)
                return
            kind, angle = self.placement
            if 0 <= world.x <= self.project.hall_length and 0 <= world.y <= self.project.hall_width:
                before = deepcopy(self.project); before_connector = self.active_connector; before_selection = self._selection_state()
                element = TrackElement(kind, world, width=self.default_width, length=self.default_length,
                                       radius=self.default_radius, angle_deg=angle or 45.0)
                if not self.project.element_fits_hall(element):
                    self.status_message.emit(self._tr("The element would extend beyond the hall."))
                    return
                if self._would_overlap(element):
                    self.status_message.emit(self._tr("Track elements may not overlap."))
                    return
                self.project.elements.append(element)
                self.selected = element; self.selected_ids = {element.id}
                self.active_connector = ConnectorRef(element.id, "end")
                self._commit_change(self._tr("Place element"), before, before_selection, before_connector)
            return
        connector = self._connector_at(event.position())
        if connector:
            element = self.project.element_by_id(connector.element_id)
            self.selected = element
            self.selected_ids = {element.id}
            self.active_connector = connector if self.project.is_free(connector) else None
            if self.active_connector is None:
                self.status_message.emit(self._tr(
                    "Connected connector: double-click or right-click to disconnect."
                ))
            self.selection_changed.emit(element); self.update()
            return
        clicked = self._hit_test(event.position())
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and clicked:
            if clicked.id in self.selected_ids and len(self.selected_ids) > 1:
                self.selected_ids.remove(clicked.id)
                self.selected = self.project.element_by_id(next(iter(self.selected_ids)))
            else:
                self.selected_ids.add(clicked.id); self.selected = clicked
            self._dragging_element = False
            self.selection_changed.emit(self.selected); self.update(); return
        if not clicked:
            self._selecting_rect = True
            self._rubber_origin = event.position().toPoint()
            self._rubber_additive = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if not self._rubber_additive:
                self.selected_ids.clear(); self.selected = None
            self._rubber_band.setGeometry(QRect(self._rubber_origin, self._rubber_origin))
            self._rubber_band.show()
            self._dragging_element = False
            self.selection_changed.emit(self.selected); self.update(); return
        if clicked and clicked.id not in self.selected_ids:
            self.selected_ids = {clicked.id}
        self.selected = clicked
        self._dragging_element = self.selected is not None
        self._drag_started = False
        self._drag_before = deepcopy(self.project) if self.selected else None
        self._drag_before_connector = self.active_connector
        self._drag_before_selection = self._selection_state()
        self.selection_changed.emit(self.selected)
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            connector = self._connector_at(event.position())
            if connector and self.project.connection_for(connector):
                self.disconnect_connector(connector)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        connector = self._connector_at(event.pos())
        if connector and self.project.connection_for(connector):
            menu = QMenu(self)
            disconnect_action = menu.addAction(self._tr("Disconnect connection"))
            if menu.exec(event.globalPos()) is disconnect_action:
                self.disconnect_connector(connector)
            event.accept()
            return
        super().contextMenuEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        delta = event.position().toPoint() - self._last_mouse
        self._last_mouse = event.position().toPoint()
        if self._panning:
            self.pan += QPointF(delta)
            self.update()
        elif self._selecting_rect:
            self._rubber_band.setGeometry(QRect(
                self._rubber_origin, event.position().toPoint()).normalized())
        elif self._dragging_element and self.selected:
            dx, dy = delta.x() / self.scale, -delta.y() / self.scale
            if not self._drag_started and (abs(dx) > 1e-12 or abs(dy) > 1e-12):
                for connection in list(self.project.connections):
                    first_selected = connection.first.element_id in self.selected_ids
                    second_selected = connection.second.element_id in self.selected_ids
                    if first_selected != second_selected:
                        self._drag_ignored_pairs.add(frozenset((connection.first.element_id, connection.second.element_id)))
                        self.project.connections.remove(connection)
                self._remember_initial_overlaps()
                self.active_connector = None
                self._drag_started = True
            moved_dx, moved_dy = self._move_selection_safely(dx, dy)
            self._forget_resolved_overlaps()
            candidate = self._find_snap(self.selected) if len(self.selected_ids) == 1 else None
            self.snap_preview = (candidate[1], candidate[2]) if candidate else None
            self.update()
        else:
            w = self.screen_to_world(event.position())
            self.status_message.emit(f"x {w.x:.2f} m · y {w.y:.2f} m")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._panning = False
        if self._selecting_rect:
            selection_rect = QRectF(self._rubber_band.geometry().normalized())
            matched = {
                element.id for element in self.project.elements
                if self._road_shape(element).intersects(selection_rect)
            }
            if self._rubber_additive:
                self.selected_ids.update(matched)
            else:
                self.selected_ids = matched
            self.selected = next(
                (element for element in reversed(self.project.elements)
                 if element.id in self.selected_ids), None
            )
            self._rubber_band.hide()
            self._selecting_rect = False
            self.selection_changed.emit(self.selected)
            self.status_message.emit(self._tr(
                "{count} elements selected.", count=len(self.selected_ids)
            ))
            self.update()
            return
        if self._dragging_element and self.selected and self._drag_started:
            if not self.project.element_fits_hall(self.selected):
                self._restore_without_signal(self._drag_before, self._drag_before_selection,
                                             self._drag_before_connector)
                self.selection_changed.emit(self.selected); self.update()
                self.status_message.emit(self._tr("The element would extend beyond the hall."))
            else:
                if len(self.selected_ids) == 1: self._snap_element(self.selected)
                self._commit_change(self._tr("Move element"), self._drag_before,
                                    self._drag_before_selection, self._drag_before_connector)
        self.snap_preview = None
        self._dragging_element = False
        self._drag_started = False
        self._drag_before = None
        self._drag_ignored_pairs.clear()
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
        if self._dragging_element and self.selected and self._drag_started and self._drag_before is not None:
            if self.project.element_fits_hall(self.selected):
                self._commit_change(self._tr("Move element"), self._drag_before,
                                    self._drag_before_selection, self._drag_before_connector)
            else:
                self._restore_without_signal(self._drag_before, self._drag_before_selection,
                                             self._drag_before_connector)
                self.selection_changed.emit(self.selected); self.update()
                self.status_message.emit(self._tr("The element would extend beyond the hall."))
        self._space_pressed = False
        self._panning = False
        self._selecting_rect = False
        self._rubber_band.hide()
        self._dragging_element = False
        self._drag_started = False
        self._drag_before = None
        self.snap_preview = None
        self._drag_ignored_pairs.clear()
        self.unsetCursor()
        if self.placement:
            self.setCursor(Qt.CursorShape.CrossCursor)
        super().focusOutEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._view_fitted:
            self.fit_to_view()
