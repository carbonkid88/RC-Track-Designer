"""Qt-Zeichenfläche für Darstellung und direkte Bearbeitung."""

from __future__ import annotations

from copy import deepcopy
from math import atan2, cos, degrees, hypot, radians, sin
from uuid import uuid4

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QFocusEvent, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPen, QUndoStack, QWheelEvent
from PySide6.QtWidgets import QMenu, QRubberBand, QWidget

from .commands import ProjectStateCommand
from .closure import ClosureProposal, propose_closure
from .model import ConnectorRef, PlanningObject, Point, Pose, TrackConnection, TrackElement, TrackProject
from .measuring import MeasurementState, nearest_geometry_snap
from .planning import drivers_stand_handles, draw_planning_object, planning_hit_test
from .rendering import (
    connection_bridge_polygon,
    element_centerline_path,
    element_filled_shape,
)


class TrackCanvas(QWidget):
    project_changed = Signal()
    selection_changed = Signal(object)
    status_message = Signal(str)
    closure_connectors_changed = Signal(int)
    close_track_requested = Signal()
    measurement_mode_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.project = TrackProject()
        self.project_name = ""
        self.scale = 25.0
        self.pan = QPointF(35.0, 35.0)
        self.selected: TrackElement | None = None
        self.selected_planning: PlanningObject | None = None
        self.selected_ids: set[str] = set()
        self.placement: tuple[str, float] | None = None
        self.planning_placement: tuple[str, float] | None = None
        self.planning_draft_start: Point | None = None
        self.planning_draft_preview: Point | None = None
        self.planning_draft_axis_deg: float | None = None
        self.planning_snap_preview: Point | None = None
        self._dragging_planning = False
        self._planning_drag_before = None
        self._planning_drag_offset: Point | None = None
        self._planning_resize_endpoint: int | None = None
        self._planning_resize_fixed: Point | None = None
        self._planning_resize_before = None
        self._planning_side_handle: str | None = None
        self._planning_side_fixed: Point | None = None
        self._planning_side_before = None
        self.default_width = 2.0
        self.default_length = 5.0
        self.default_radius = 5.0
        self._last_mouse = QPoint()
        self._dragging_element = False
        self._drag_started = False
        self._drag_before = None
        self._resize_connector: ConnectorRef | None = None
        self._resize_started = False
        self._resize_before = None
        self._resize_before_selection = None
        self._resize_before_connector = None
        self._magnet_drag_connector: ConnectorRef | None = None
        self._magnet_drag_started = False
        self._magnet_drag_before = None
        self._magnet_drag_before_selection = None
        self._magnet_drag_before_connector = None
        self._junction_drag_connector: ConnectorRef | None = None
        self._junction_drag_started = False
        self._junction_drag_before = None
        self._junction_drag_before_selection = None
        self._junction_drag_before_connector = None
        self._drag_ignored_pairs: set[frozenset[str]] = set()
        self._drag_joint_followers: set[str] = set()
        self._drag_joint_bridges: dict[str, tuple[ConnectorRef, ConnectorRef, Point]] = {}
        self._panning = False
        self._selecting_rect = False
        self._rubber_origin = QPoint()
        self._rubber_additive = False
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._ruler_size = 28.0
        self._guide_drag_axis: str | None = None
        self._guide_drag_value: float | None = None
        self._guide_drag_existing: tuple[str, int, float] | None = None
        self._guide_drag_before = None
        self._space_pressed = False
        self._view_fitted = True
        self._colors = {
            "canvas": "#202326", "hall": "#e8e8e4", "grid": "#c9c9c4",
            "track": "#555b62", "centerline": "#f7f7f7", "text": "#f3f5f7",
        }
        self._tr = lambda text, **values: text.format(**values) if values else text
        self.undo_stack = QUndoStack(self)
        self.active_connector: ConnectorRef | None = None
        self.closure_connectors: list[ConnectorRef] = []
        self.snap_distance_px = 34.0
        self.indoor_snap_distance_px = 20.0
        self.connector_hit_distance_px = 10.0
        # A modest angular tolerance makes docking helpful without undoing a
        # deliberate manual rotation from far outside the target tangent.
        self.tangent_tolerance_deg = 30.0
        self.indoor_tangent_tolerance_deg = 8.0
        self.snap_preview: tuple[ConnectorRef, ConnectorRef] | None = None
        self.measurement = MeasurementState()
        self.measure_snap_distance_px = 14.0
        self._language = "de"
        self._clipboard_elements: list[TrackElement] = []
        self._clipboard_connections: list[TrackConnection] = []
        self._paste_generation = 0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(640, 400)

    def set_project_name(self, name: str) -> None:
        """Show the loaded project name beside the fixed area information."""
        self.project_name = name.strip()
        self.update()

    def set_project(self, project: TrackProject) -> None:
        self.measurement.clear()
        self.project = project
        self.selected = None
        self.selected_planning = None
        self.selected_ids.clear()
        self.active_connector = None
        self.closure_connectors.clear()
        self.placement = None
        self.planning_placement = None
        self.planning_draft_start = None
        self.planning_draft_preview = None
        self.planning_draft_axis_deg = None
        self.planning_snap_preview = None
        self._resize_connector = None
        self._resize_started = False
        self._resize_before = None
        self._magnet_drag_connector = None
        self._magnet_drag_started = False
        self._magnet_drag_before = None
        self._junction_drag_connector = None
        self._junction_drag_started = False
        self._junction_drag_before = None
        self.undo_stack.clear()
        self.fit_to_view()
        self.selection_changed.emit(None)
        self.closure_connectors_changed.emit(0)
        self.update()

    def set_editor_mode(self, mode: str) -> None:
        if mode not in {"normal", "indoor"}:
            raise ValueError("Unknown editor mode")
        if self.project.editor_mode == mode:
            return
        before = deepcopy(self.project)
        before_selection = self._selection_state()
        before_connector = self.active_connector
        self.project.editor_mode = mode
        self.placement = None
        self.unsetCursor()
        self.clear_selection()
        self._commit_change(self._tr("Change editor mode"), before,
                            before_selection, before_connector)

    def fit_to_view(self) -> None:
        margin = 72.0
        if self.width() > 100 and self.height() > 100:
            self.scale = max(2.0, min((self.width() - 2 * margin) / self.project.hall_length,
                                      (self.height() - 2 * margin) / self.project.hall_width))
        hall_pixels_w = self.project.hall_length * self.scale
        hall_pixels_h = self.project.hall_width * self.scale
        self.pan = QPointF((self.width() - hall_pixels_w + self._ruler_size) / 2,
                           (self.height() - hall_pixels_h + self._ruler_size) / 2)
        self._view_fitted = True
        self.update()

    def set_appearance(self, colors: dict[str, str], translator=None,
                       language: str | None = None) -> None:
        self._colors.update(colors)
        if translator:
            self._tr = translator
        if language:
            self._language = language
        self.update()

    def set_measurement_mode(self, active: bool) -> None:
        """Enter or leave the non-destructive temporary measuring tool."""
        active = bool(active)
        self.measurement.clear()
        if self.measurement.active == active:
            self.update()
            return
        self.measurement.active = active
        self.placement = None
        self.planning_placement = None
        self.planning_draft_start = None
        self.planning_draft_preview = None
        self.planning_draft_axis_deg = None
        self.planning_snap_preview = None
        self.clear_selection()
        if active:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.unsetCursor()
        self.status_message.emit(self._tr(
            "Click the first measurement point."
            if active else "Selection mode"
        ))
        self.measurement_mode_changed.emit(active)
        self.update()

    def clear_measurement(self) -> None:
        self.measurement.clear()
        if self.measurement.active:
            self.status_message.emit(self._tr("Click the first measurement point."))
        self.update()

    def exit_measurement(self) -> None:
        self.set_measurement_mode(False)

    def _measurement_point(self, screen_point: QPointF) -> Point:
        world = self.screen_to_world(screen_point)
        snap = nearest_geometry_snap(
            self.project,
            world,
            self.measure_snap_distance_px / self.scale,
        )
        self.measurement.snap_point = snap.point if snap else None
        return snap.point if snap else world

    def _set_measurement_point(self, screen_point: QPointF) -> None:
        point = self._measurement_point(screen_point)
        if self.measurement.start is None:
            self.measurement.start = point
            self.measurement.preview = point
            self.status_message.emit(self._tr("Click the second measurement point."))
        elif self.measurement.end is None:
            self.measurement.end = point
            self.measurement.preview = None
            self.status_message.emit(self._tr(
                "Measured distance: {distance} m",
                distance=self._format_measurement(self.measurement.distance or 0.0),
            ))
        self.update()

    def _format_measurement(self, distance: float) -> str:
        text = f"{distance:.2f}"
        return text.replace(".", ",") if self._language == "de" else text

    def _draw_measurement(self, painter: QPainter) -> None:
        if not self.measurement.active:
            return
        if self.measurement.snap_point is not None:
            snap = self.world_to_screen(self.measurement.snap_point)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#ffb020"), 2))
            painter.drawEllipse(snap, 7, 7)
        if self.measurement.start is None:
            return
        target = self.measurement.end or self.measurement.preview
        start = self.world_to_screen(self.measurement.start)
        painter.setPen(QPen(QColor("#26c6da"), 2, Qt.PenStyle.SolidLine))
        painter.setBrush(QColor("#26c6da"))
        painter.drawEllipse(start, 4, 4)
        if target is not None:
            end = self.world_to_screen(target)
            painter.drawLine(start, end)
            painter.drawEllipse(end, 4, 4)
            distance = hypot(target.x - self.measurement.start.x,
                             target.y - self.measurement.start.y)
            label_text = f"{self._format_measurement(distance)} m"
            font = painter.font()
            font.setPixelSize(13)
            font.setBold(True)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            midpoint = (start + end) / 2
            label = QRectF(
                midpoint.x() - metrics.horizontalAdvance(label_text) / 2 - 5,
                midpoint.y() - metrics.height() - 7,
                metrics.horizontalAdvance(label_text) + 10,
                metrics.height() + 4,
            )
            painter.fillRect(label, QColor(20, 24, 28, 220))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, label_text)

    def world_to_screen(self, p: Point) -> QPointF:
        return QPointF(self.pan.x() + p.x * self.scale,
                       self.pan.y() + (self.project.hall_width - p.y) * self.scale)

    def screen_to_world(self, p: QPointF) -> Point:
        return Point((p.x() - self.pan.x()) / self.scale,
                     self.project.hall_width - (p.y() - self.pan.y()) / self.scale)

    def set_placement(self, kind: str, angle: float = 0.0) -> None:
        if self.measurement.active:
            self.status_message.emit(self._tr(
                "Clear or exit the measurement before editing elements."
            ))
            return
        self.planning_placement = None
        self.planning_draft_start = None
        self.planning_draft_preview = None
        self.planning_draft_axis_deg = None
        self.planning_snap_preview = None
        active_element = (self.project.element_by_id(self.active_connector.element_id)
                          if self.active_connector else None)
        wanted_type = "boundary" if self.project.editor_mode == "indoor" else "track"
        if (self.active_connector and self.project.can_accept_connection(self.active_connector)
                and active_element and active_element.element_type == wanted_type):
            self._append_to_active(kind, angle or 45.0)
            return
        self.placement = (kind, angle)
        self.setCursor(Qt.CursorShape.CrossCursor)
        if kind == "straight":
            label = self._tr("straight")
        else:
            label = self._tr("curve {angle}°", angle=f"{angle:g}")
        self.status_message.emit(self._tr("Click inside the track area to place {element}; Esc cancels.", element=label))
        self.update()

    def set_planning_placement(self, kind: str, length: float = 2.0) -> None:
        if kind not in {"start_finish", "timing_loop", "starting_grid", "drivers_stand"}:
            raise ValueError("Unknown planning object type")
        if self.measurement.active:
            self.exit_measurement()
        self.placement = None
        self.clear_selection()
        self.planning_placement = (kind, max(0.1, float(length)))
        self.planning_draft_start = None
        self.planning_draft_preview = None
        self.planning_draft_axis_deg = None
        self.planning_snap_preview = None
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.status_message.emit(self._tr("Click inside the track area to place the marker."))

    def cancel_planning_placement(self) -> None:
        self.planning_placement = None
        self.planning_draft_start = None
        self.planning_draft_preview = None
        self.planning_draft_axis_deg = None
        self.planning_snap_preview = None
        self.unsetCursor()
        self.status_message.emit(self._tr("Selection mode"))
        self.update()

    def cancel_placement(self) -> None:
        self.placement = None
        self.unsetCursor()
        self.status_message.emit(self._tr("Selection mode"))
        self.update()

    def _constrain_planning_draft(self, point: Point) -> Point:
        """Soft-snap a marker to perpendicular only inside the 85-95° window."""
        if self.planning_draft_start is None or self.planning_draft_axis_deg is None:
            return point
        angle = radians(self.planning_draft_axis_deg)
        axis_x, axis_y = cos(angle), sin(angle)
        dx = point.x - self.planning_draft_start.x
        dy = point.y - self.planning_draft_start.y
        if hypot(dx, dy) <= 1e-12:
            return point
        pointer_angle = degrees(atan2(dy, dx)) % 180
        axis_angle = self.planning_draft_axis_deg % 180
        difference = abs(pointer_angle - axis_angle)
        difference = min(difference, 180 - difference)
        if difference > 5.0:
            return point
        distance = dx * axis_x + dy * axis_y
        return Point(
            self.planning_draft_start.x + distance * axis_x,
            self.planning_draft_start.y + distance * axis_y,
        )

    def clear_selection(self) -> None:
        self.selected = None
        self.selected_planning = None
        self.selected_ids.clear()
        self.active_connector = None
        self.snap_preview = None
        self.closure_connectors.clear()
        self.closure_connectors_changed.emit(0)
        self.selection_changed.emit(None)
        self.status_message.emit(self._tr("Selection mode"))
        self.update()

    def _planning_at(self, position: QPointF) -> PlanningObject | None:
        return next((item for item in reversed(self.project.planning_objects)
                     if planning_hit_test(item, position, self.world_to_screen)), None)

    def _planning_endpoint_at(
        self, position: QPointF,
    ) -> tuple[PlanningObject, int] | None:
        for item in reversed(self.project.planning_objects):
            if item.kind in {"starting_grid", "drivers_stand"}:
                continue
            for index, endpoint in enumerate(item.endpoints):
                screen = self.world_to_screen(endpoint)
                if hypot(screen.x() - position.x(), screen.y() - position.y()) <= 8:
                    return item, index
        return None

    def _drivers_stand_handle_at(self, position: QPointF) -> str | None:
        item = self.selected_planning
        if not item or item.kind != "drivers_stand" or item.locked:
            return None
        for name, point in drivers_stand_handles(item).items():
            screen = self.world_to_screen(point)
            if hypot(screen.x() - position.x(), screen.y() - position.y()) <= 9:
                return name
        return None

    def _planning_snap_point(self, point: Point) -> Point | None:
        """Prefer explicit connector/magnet points over nearby contours."""
        tolerance = self.measure_snap_distance_px / self.scale
        connector_candidates: list[tuple[float, Point]] = []
        for element in self.project.elements:
            for endpoint in element.connector_names:
                candidate = element.pose_at(endpoint).point
                distance = hypot(candidate.x - point.x, candidate.y - point.y)
                if distance <= tolerance:
                    connector_candidates.append((distance, candidate))
        if connector_candidates:
            return min(connector_candidates, key=lambda candidate: candidate[0])[1]
        contour_snap = nearest_geometry_snap(self.project, point, tolerance)
        return contour_snap.point if contour_snap else None

    @staticmethod
    def _set_planning_endpoints(
        item: PlanningObject, first: Point, second: Point,
    ) -> bool:
        dx, dy = second.x - first.x, second.y - first.y
        length = hypot(dx, dy)
        if length < 0.05:
            return False
        item.center = Point((first.x + second.x) / 2, (first.y + second.y) / 2)
        item.length = length
        item.heading_deg = (degrees(atan2(dy, dx)) - 90) % 360
        return True

    def _snap_planning_to_straight(self, item: PlanningObject) -> bool:
        """Magnetically centre and orient a marker across a nearby straight."""
        if item.kind in {"starting_grid", "drivers_stand"}:
            return False
        best: tuple[float, Point, TrackElement] | None = None
        extra_tolerance = self._current_snap_distance() / self.scale
        for element in self.project.elements:
            if element.kind != "straight":
                continue
            if self._angle_difference(item.heading_deg, element.heading_deg) > 5.0:
                continue
            end = element.end_pose.point
            dx, dy = end.x - element.start.x, end.y - element.start.y
            length_squared = dx * dx + dy * dy
            if length_squared <= 1e-12:
                continue
            fraction = max(0.0, min(1.0, (
                (item.center.x - element.start.x) * dx
                + (item.center.y - element.start.y) * dy
            ) / length_squared))
            point = Point(element.start.x + fraction * dx,
                          element.start.y + fraction * dy)
            distance = hypot(item.center.x - point.x, item.center.y - point.y)
            tolerance = element.width / 2 + extra_tolerance
            if distance <= tolerance and (best is None or distance < best[0]):
                best = (distance, point, element)
        if best is None:
            return False
        _distance, point, element = best
        item.center = point
        item.heading_deg = element.heading_deg
        return True

    def toggle_selected_planning_lock(self) -> None:
        if not self.selected_planning:
            return
        before = deepcopy(self.project)
        before_selection = self._selection_state()
        self.selected_planning.locked = not self.selected_planning.locked
        self._commit_change(
            self._tr("Lock marker" if self.selected_planning.locked else "Unlock marker"),
            before, before_selection, None,
        )
        if (self.selected_planning and self.selected_planning.locked
                and self.selected_planning.kind != "drivers_stand"):
            self.clear_selection()
        else:
            self.selection_changed.emit(self.selected_planning)
            self.update()

    def toggle_closure_connector(self, connector: ConnectorRef) -> None:
        if not self.project.is_free(connector):
            return
        if connector in self.closure_connectors:
            self.closure_connectors.remove(connector)
        else:
            if len(self.closure_connectors) >= 2:
                self.closure_connectors.clear()
            self.closure_connectors.append(connector)
        self.closure_connectors_changed.emit(len(self.closure_connectors))
        self.status_message.emit(self._tr(
            "{count} of 2 free connectors selected for closing.",
            count=len(self.closure_connectors),
        ))
        self.update()

    def prepare_track_closure(self) -> ClosureProposal | None:
        if len(self.closure_connectors) != 2:
            return None
        return propose_closure(self.project, *self.closure_connectors)

    def apply_track_closure(self, proposal: ClosureProposal) -> None:
        before = deepcopy(self.project)
        before_selection = self._selection_state()
        before_connector = self.active_connector
        selected_id, selected_ids = before_selection
        self.project = deepcopy(proposal.project)
        self.selected_ids = {item for item in selected_ids
                             if self.project.element_by_id(item)}
        self.selected = self.project.element_by_id(selected_id) if selected_id else None
        self.active_connector = None
        self.closure_connectors.clear()
        self.closure_connectors_changed.emit(0)
        self._commit_change(self._tr("Close track"), before,
                            before_selection, before_connector)

    def rotate_selected(self, degrees: float) -> None:
        if self.selected_planning:
            if self.selected_planning.locked:
                return
            before = deepcopy(self.project)
            before_selection = self._selection_state()
            self.selected_planning.rotate(degrees)
            if not self.selected_planning.fits_hall(
                self.project.hall_length, self.project.hall_width
            ):
                self._restore_without_signal(before, before_selection, None)
                self.status_message.emit(self._tr("The object would extend beyond the track area."))
                return
            self._commit_change(self._tr("Rotate marker"), before, before_selection, None)
            return
        if self.selected:
            before = deepcopy(self.project)
            before_connector = self.active_connector
            before_selection = self._selection_state()
            self.project.disconnect_element(self.selected.id)
            self.selected.rotate(degrees)
            if not self.project.element_fits_hall(self.selected):
                self._restore_without_signal(before, self.selected.id, before_connector)
                self.status_message.emit(self._tr("The element would extend beyond the track area."))
                return
            self.active_connector = None
            self.selected_ids = {self.selected.id}
            self._commit_change(self._tr("Rotate element"), before, before_selection, before_connector)

    def can_rotate_selected(self, degrees: float) -> bool:
        if self.selected_planning:
            return not self.selected_planning.locked
        return bool(self.selected and self.manual_heading_allowed(
            self.selected, self.selected.heading_deg + degrees))

    @staticmethod
    def manual_heading_allowed(element: TrackElement, heading_deg: float) -> bool:
        return True

    def delete_selected(self) -> None:
        if self.selected_planning:
            before = deepcopy(self.project)
            before_selection = self._selection_state()
            self.project.planning_objects.remove(self.selected_planning)
            self.selected_planning = None
            self.selection_changed.emit(None)
            self._commit_change(self._tr("Delete marker"), before, before_selection, None)
            return
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

    def copy_selected(self) -> None:
        ids = self.selected_ids or ({self.selected.id} if self.selected else set())
        if not ids:
            return
        self._clipboard_elements = deepcopy([
            element for element in self.project.elements if element.id in ids
        ])
        self._clipboard_connections = deepcopy([
            connection for connection in self.project.connections
            if connection.first.element_id in ids and connection.second.element_id in ids
        ])
        self._paste_generation = 0
        self.status_message.emit(self._tr(
            "{count} elements copied.", count=len(self._clipboard_elements)
        ))

    def paste_copied(self) -> None:
        if not self._clipboard_elements:
            return
        before = deepcopy(self.project)
        before_selection = self._selection_state()
        before_connector = self.active_connector
        copies = deepcopy(self._clipboard_elements)
        id_map: dict[str, str] = {}
        for element in copies:
            old_id = element.id
            element.id = str(uuid4())
            id_map[old_id] = element.id
        self._paste_generation += 1
        requested = 0.5 * self._paste_generation
        dx, dy = self.project.clamp_group_translation(copies, requested, requested)
        for element in copies:
            element.moved(dx, dy)
        self.project.elements.extend(copies)
        for connection in self._clipboard_connections:
            first = ConnectorRef(id_map[connection.first.element_id], connection.first.endpoint)
            second = ConnectorRef(id_map[connection.second.element_id], connection.second.endpoint)
            self.project.connect(first, second)
        self.selected_ids = {element.id for element in copies}
        self.selected = copies[-1]
        self.active_connector = None
        self._commit_change(self._tr("Paste elements"), before, before_selection, before_connector)
        self.status_message.emit(self._tr(
            "{count} elements pasted.", count=len(copies)
        ))

    def change_selected(self, text: str, **values: float) -> None:
        if self.selected_planning:
            item = self.selected_planning
            if item.locked:
                return
            before = deepcopy(self.project)
            before_selection = self._selection_state()
            if "x" in values or "y" in values:
                item.center = Point(values.get("x", item.center.x),
                                    values.get("y", item.center.y))
            if "length" in values:
                item.length = max(0.1, values["length"])
            if "width" in values:
                item.width = max(0.1, values["width"])
            if "heading_deg" in values:
                item.heading_deg = values["heading_deg"] % 360
            if not item.fits_hall(self.project.hall_length, self.project.hall_width):
                self._restore_without_signal(before, before_selection, None)
                self.status_message.emit(self._tr("The object would extend beyond the track area."))
                return
            self._commit_change(text, before, before_selection, None)
            return
        if not self.selected: return
        before = deepcopy(self.project); before_connector = self.active_connector; before_selection = self._selection_state()
        geometry_change = bool({"length", "radius", "angle_deg"} & values.keys())
        pose_change = bool({"x", "y", "heading_deg"} & values.keys())
        connected_endpoints = [
            endpoint for endpoint in ("start", "end")
            if self.project.connection_for(ConnectorRef(self.selected.id, endpoint))
        ]
        if geometry_change and not pose_change and len(connected_endpoints) == 2:
            self.status_message.emit(self._tr(
                "Disconnect one endpoint before changing this element's geometry."
            ))
            self.selection_changed.emit(self.selected)
            return
        fixed_endpoint = connected_endpoints[0] if geometry_change and not pose_change and len(connected_endpoints) == 1 else None
        fixed_pose = self.selected.pose_at(fixed_endpoint) if fixed_endpoint else None
        if pose_change:
            self.project.disconnect_element(self.selected.id)
        if "x" in values or "y" in values:
            self.selected.start = Point(values.get("x", self.selected.start.x), values.get("y", self.selected.start.y))
        for name in ("width", "length", "radius", "angle_deg"):
            if name in values: setattr(self.selected, name, values[name])
        if not self.selected.has_valid_road_geometry:
            required_radius = self.selected.minimum_centerline_radius
            self._restore_without_signal(before, before_selection, before_connector)
            self.selection_changed.emit(self.selected); self.update()
            self.status_message.emit(self._tr(
                "The centerline radius must be at least {radius:.2f} m for this track width.",
                radius=required_radius,
            ))
            return
        if "heading_deg" in values:
            target = values["heading_deg"] % 360
            delta = (target - self.selected.heading_deg + 180) % 360 - 180
            self.selected.rotate(delta)
        if fixed_endpoint and fixed_pose:
            self.selected.align_endpoint(fixed_endpoint, fixed_pose)
        if not self.project.element_fits_hall(self.selected):
            selected_id = self.selected.id
            self._restore_without_signal(before, selected_id, before_connector)
            self.selection_changed.emit(self.selected); self.update()
            self.status_message.emit(self._tr("The element would extend beyond the track area."))
            return
        if fixed_endpoint:
            self.active_connector = ConnectorRef(
                self.selected.id, "end" if fixed_endpoint == "start" else "start"
            )
        elif pose_change:
            self.active_connector = None
        self.selected_ids = {self.selected.id}
        self._commit_change(text, before, before_selection, before_connector)

    def disconnect_connector(self, connector: ConnectorRef) -> bool:
        connection = self.project.connection_for(connector)
        if connection is None: return False
        before = deepcopy(self.project); before_selection = self._selection_state(); before_connector = self.active_connector
        self.project.disconnect_all(connector)
        self.selected = self.project.element_by_id(connector.element_id)
        self.selected_ids = {connector.element_id}
        self.active_connector = connector
        self._commit_change(self._tr("Disconnect track elements"), before, before_selection, before_connector)
        self.status_message.emit(self._tr("Connection released; the selected connector is now active."))
        return True

    def _selection_id(self) -> str | None:
        if self.selected_planning:
            return f"planning:{self.selected_planning.id}"
        return self.selected.id if self.selected else None

    def _selection_state(self):
        ids = self.selected_ids or ({self.selected.id} if self.selected else set())
        return self._selection_id(), tuple(sorted(ids))

    def _restore_state(self, project: TrackProject, selection, connector: ConnectorRef | None) -> None:
        self._restore_without_signal(project, selection, connector)
        self.selection_changed.emit(self.selected_planning or self.selected)
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
        planning_id = (selected_id.split(":", 1)[1]
                       if isinstance(selected_id, str) and selected_id.startswith("planning:")
                       else None)
        self.selected_planning = project.planning_object_by_id(planning_id) if planning_id else None
        self.selected = (None if planning_id else
                         project.element_by_id(selected_id) if selected_id else None)
        self.active_connector = (connector if connector
                                 and project.can_accept_connection(connector) else None)

    def _commit_change(self, text: str, before: TrackProject, before_selection,
                       before_connector: ConnectorRef | None) -> None:
        command = ProjectStateCommand(text, before, self.project, before_selection, self._selection_state(),
                                      before_connector, self.active_connector, self._restore_state)
        self.undo_stack.push(command)
        self.selection_changed.emit(self.selected_planning or self.selected)
        self.project_changed.emit(); self.update()

    @staticmethod
    def _angle_difference(first: float, second: float) -> float:
        return abs((first - second + 180) % 360 - 180)

    def _current_snap_distance(self) -> float:
        return (self.indoor_snap_distance_px
                if self.project.editor_mode == "indoor" else self.snap_distance_px)

    def _connector_at(self, pos: QPointF, free_only: bool = False) -> ConnectorRef | None:
        best = None
        best_key = (self.connector_hit_distance_px, 1)
        for element in self.project.elements:
            for endpoint in element.connector_names:
                connector = ConnectorRef(element.id, endpoint)
                if free_only and not self.project.can_accept_connection(connector): continue
                screen = self.world_to_screen(element.pose_at(endpoint).point)
                distance = hypot(screen.x() - pos.x(), screen.y() - pos.y())
                priority = 0 if endpoint.startswith("magnet:") else 1
                key = (distance, priority)
                if distance <= self.connector_hit_distance_px and key < best_key:
                    best, best_key = connector, key
        return best

    def _free_connector_at_excluding(self, pos: QPointF,
                                     excluded: ConnectorRef,
                                     maximum_distance: float | None = None) -> ConnectorRef | None:
        best = None
        limit = (self.connector_hit_distance_px if maximum_distance is None
                 else maximum_distance)
        best_key = (limit, 1)
        for element in self.project.elements:
            if element.id == excluded.element_id:
                continue
            excluded_element = self.project.element_by_id(excluded.element_id)
            if excluded_element and element.element_type != excluded_element.element_type:
                continue
            for endpoint in element.connector_names:
                connector = ConnectorRef(element.id, endpoint)
                if not self.project.can_accept_connection(connector):
                    continue
                screen = self.world_to_screen(element.pose_at(endpoint).point)
                distance = hypot(screen.x() - pos.x(), screen.y() - pos.y())
                priority = 0 if endpoint.startswith("magnet:") else 1
                key = (distance, priority)
                if distance <= limit and key < best_key:
                    best, best_key = connector, key
        return best

    def _append_to_active(self, kind: str, angle: float) -> None:
        connector = self.active_connector
        if not connector or not self.project.can_accept_connection(connector): return
        before = deepcopy(self.project); before_connector = connector; before_selection = self._selection_state()
        target = self.project.connector_pose(connector)
        source_element = self.project.element_by_id(connector.element_id)
        wanted_type = "boundary" if self.project.editor_mode == "indoor" else "track"
        if source_element is None or source_element.element_type != wanted_type:
            return
        kinds = ("left", "right") if kind == "curve" else (kind,)
        preferred_endpoint = "start" if connector.endpoint == "end" else "end"
        endpoints = (preferred_endpoint,
                     "end" if preferred_endpoint == "start" else "start")
        candidates = []
        for candidate_kind in kinds:
            for endpoint_priority, new_endpoint in enumerate(endpoints):
                element = TrackElement(
                    candidate_kind, target.point, width=self.default_width,
                    length=self.default_length, radius=self.default_radius,
                    angle_deg=angle, element_type=wanted_type,
                )
                new_connector = ConnectorRef(element.id, new_endpoint)
                aligned_target = TrackProject.connection_target_pose(
                    new_connector, connector, target
                )
                element.align_endpoint(new_endpoint, aligned_target)
                if not self.project.element_fits_hall(element):
                    continue
                overlaps = sum(
                    1 for other in self.project.elements
                    if other.id != connector.element_id
                    and self._shapes_overlap(self._road_shape(element),
                                             self._road_shape(other))
                )
                candidates.append((overlaps, endpoint_priority,
                                   element, new_connector))
        if not candidates:
            self.status_message.emit(self._tr("The element would extend beyond the track area."))
            return
        _overlaps, _priority, element, new_connector = min(
            candidates, key=lambda item: (item[0], item[1])
        )
        self.project.elements.append(element)
        self.project.connect(connector, new_connector)
        self.selected = element; self.selected_ids = {element.id}
        self.active_connector = ConnectorRef(
            element.id, "end" if new_connector.endpoint == "start" else "start"
        )
        self._commit_change(self._tr("Add connected element"), before, before_selection, before_connector)

    def _find_snap(self, element: TrackElement):
        best = None
        for own_endpoint in ("start", "end"):
            own = ConnectorRef(element.id, own_endpoint)
            if not self.project.is_free(own): continue
            pose = element.pose_at(own_endpoint); screen = self.world_to_screen(pose.point)
            for other in self.project.elements:
                if other.id == element.id: continue
                if other.element_type != element.element_type: continue
                for candidate_endpoint in other.connector_names:
                    candidate = ConnectorRef(other.id, candidate_endpoint)
                    if not self.project.can_accept_connection(candidate): continue
                    stationary = other.pose_at(candidate_endpoint)
                    target = TrackProject.connection_target_pose(
                        own, candidate, stationary
                    )
                    target_screen = self.world_to_screen(target.point)
                    distance = hypot(screen.x() - target_screen.x(), screen.y() - target_screen.y())
                    angle = self._angle_difference(pose.heading_deg, target.heading_deg)
                    if (element.element_type == "boundary"
                            and angle > self.indoor_tangent_tolerance_deg):
                        target = Pose(target.point, pose.heading_deg)
                    if distance <= self._current_snap_distance():
                        score = distance + angle * 0.02
                        if best is None or score < best[0]: best = (score, own, candidate, target)
        return best

    def _find_group_snap(self):
        """Find a free outer connector for a rigid multi-element selection."""
        best = None
        selected_ids = self.selected_ids
        if len(selected_ids) < 2:
            return None
        for element in self.project.elements:
            if element.id not in selected_ids:
                continue
            for own_endpoint in ("start", "end"):
                own = ConnectorRef(element.id, own_endpoint)
                if not self.project.is_free(own):
                    continue
                pose = element.pose_at(own_endpoint)
                screen = self.world_to_screen(pose.point)
                for other in self.project.elements:
                    if other.id in selected_ids:
                        continue
                    if other.element_type != element.element_type:
                        continue
                    for candidate_endpoint in other.connector_names:
                        candidate = ConnectorRef(other.id, candidate_endpoint)
                        if not self.project.can_accept_connection(candidate):
                            continue
                        stationary = other.pose_at(candidate_endpoint)
                        target = TrackProject.connection_target_pose(
                            own, candidate, stationary
                        )
                        target_screen = self.world_to_screen(target.point)
                        distance = hypot(screen.x() - target_screen.x(),
                                         screen.y() - target_screen.y())
                        angle = self._angle_difference(pose.heading_deg,
                                                       target.heading_deg)
                        if (element.element_type == "boundary"
                                and angle > self.indoor_tangent_tolerance_deg):
                            target = Pose(target.point, pose.heading_deg)
                        if distance <= self._current_snap_distance():
                            score = distance + angle * 0.02
                            if best is None or score < best[0]:
                                best = (score, own, candidate, target)
        return best

    def _find_dual_boundary_snap(self, element: TrackElement):
        """Find two simultaneous targets for the free ends of a boundary straight."""
        if element.element_type != "boundary" or element.kind != "straight":
            return None
        choices: dict[str, list[tuple[float, ConnectorRef]]] = {
            "start": [], "end": [],
        }
        for endpoint in ("start", "end"):
            own = ConnectorRef(element.id, endpoint)
            if not self.project.is_free(own):
                return None
            screen = self.world_to_screen(element.pose_at(endpoint).point)
            for other in self.project.elements:
                if other.id == element.id or other.element_type != "boundary":
                    continue
                for candidate_endpoint in other.connector_names:
                    candidate = ConnectorRef(other.id, candidate_endpoint)
                    if not self.project.can_accept_connection(candidate):
                        continue
                    target = other.pose_at(candidate_endpoint).point
                    target_screen = self.world_to_screen(target)
                    distance = hypot(screen.x() - target_screen.x(),
                                     screen.y() - target_screen.y())
                    if distance <= self._current_snap_distance():
                        priority = 0 if candidate_endpoint.startswith("magnet:") else 1
                        choices[endpoint].append((distance + priority * 0.001,
                                                  candidate))
        best = None
        for start_score, start_target in choices["start"]:
            start_point = self.project.connector_pose(start_target).point
            for end_score, end_target in choices["end"]:
                if end_target == start_target:
                    continue
                end_point = self.project.connector_pose(end_target).point
                length = hypot(end_point.x - start_point.x,
                               end_point.y - start_point.y)
                if not 0.1 <= length <= 200:
                    continue
                score = start_score + end_score
                if best is None or score < best[0]:
                    best = (score, start_target, end_target,
                            start_point, end_point)
        return best

    def _snap_group(self) -> bool:
        best = self._find_group_snap()
        if not best:
            return False
        _score, own, candidate, target = best
        source = self.project.connector_pose(own)
        delta = (target.heading_deg - source.heading_deg + 180) % 360 - 180
        angle = radians(delta)
        pivot = source.point
        selected = [element for element in self.project.elements
                    if element.id in self.selected_ids]
        original = deepcopy(selected)
        for element in selected:
            dx, dy = element.start.x - pivot.x, element.start.y - pivot.y
            element.start = Point(
                pivot.x + dx * cos(angle) - dy * sin(angle),
                pivot.y + dx * sin(angle) + dy * cos(angle),
            )
            element.heading_deg = (element.heading_deg + delta) % 360
            if element.rotation_reference_deg is not None:
                element.rotation_reference_deg = (
                    element.rotation_reference_deg + delta
                ) % 360
        aligned_source = self.project.connector_pose(own).point
        move_x = target.point.x - aligned_source.x
        move_y = target.point.y - aligned_source.y
        for element in selected:
            element.moved(move_x, move_y)
        if not all(self.project.element_fits_hall(element) for element in selected):
            for element, prior in zip(selected, original):
                element.start = prior.start
                element.heading_deg = prior.heading_deg
                element.rotation_reference_deg = prior.rotation_reference_deg
            self.status_message.emit(self._tr(
                "The element would extend beyond the track area."
            ))
            return False
        self.project.connect(own, candidate)
        self.active_connector = None
        self.status_message.emit(self._tr("Element group snapped into place."))
        return True

    def _snap_element(self, element: TrackElement) -> bool:
        dual = self._find_dual_boundary_snap(element)
        if dual:
            _score, start_target, end_target, start_point, end_point = dual
            original = deepcopy(element)
            element.start = start_point
            element.heading_deg = degrees(atan2(
                end_point.y - start_point.y, end_point.x - start_point.x
            )) % 360
            element.length = hypot(end_point.x - start_point.x,
                                   end_point.y - start_point.y)
            element.rotation_reference_deg = element.heading_deg
            if not self.project.element_fits_hall(element):
                self._restore_element_geometry(element, original)
                return False
            self.project.connect(ConnectorRef(element.id, "start"), start_target)
            self.project.connect(ConnectorRef(element.id, "end"), end_target)
            self.active_connector = None
            self.status_message.emit(self._tr("Element snapped into place."))
            return True
        best = self._find_snap(element)
        if not best: return False
        _, own, candidate, target = best
        original_start = element.start
        original_heading = element.heading_deg
        original_reference = element.rotation_reference_deg
        element.align_endpoint(own.endpoint, target)
        if not self.project.element_fits_hall(element):
            element.start = original_start
            element.heading_deg = original_heading
            element.rotation_reference_deg = original_reference
            self.status_message.emit(self._tr("The element would extend beyond the track area."))
            return False
        self.project.connect(own, candidate)
        self.active_connector = ConnectorRef(element.id, "end" if own.endpoint == "start" else "start")
        self.status_message.emit(self._tr("Element snapped into place."))
        return True

    def _snap_jointed_boundary(self, element: TrackElement) -> bool:
        """Translate a dragged jointed boundary onto a target without rotating it."""
        best = self._find_snap(element)
        if not best:
            return False
        _score, own, candidate, target = best
        source = element.pose_at(own.endpoint).point
        dx, dy = target.point.x - source.x, target.point.y - source.y
        moved_dx, moved_dy = self._move_selection_safely(dx, dy)
        if abs(moved_dx - dx) > 1e-9 or abs(moved_dy - dy) > 1e-9:
            return False
        snapped = element.pose_at(own.endpoint).point
        if hypot(snapped.x - target.point.x, snapped.y - target.point.y) > 1e-6:
            return False
        self.project.connect(own, candidate)
        self.active_connector = ConnectorRef(
            element.id, "end" if own.endpoint == "start" else "start"
        )
        self.status_message.emit(self._tr("Element snapped into place."))
        return True

    def _element_path(self, element: TrackElement) -> QPainterPath:
        return element_centerline_path(element, self.world_to_screen, self.scale)

    def _road_shape(self, element: TrackElement) -> QPainterPath:
        return element_filled_shape(
            element,
            self.world_to_screen,
            self.scale,
            width_adjustment=0.5,
        )

    @staticmethod
    def _shapes_overlap(first: QPainterPath, second: QPainterPath) -> bool:
        bounds = first.intersected(second).boundingRect()
        return bounds.width() * bounds.height() > 0.25

    def _would_overlap(self, element: TrackElement, ignored_ids: set[str] | None = None) -> bool:
        ignored_ids = ignored_ids or set()
        shape = self._road_shape(element)
        return any(other.id not in ignored_ids and self._shapes_overlap(shape, self._road_shape(other))
                   for other in self.project.elements if other.id != element.id)

    def overlapping_element_ids(self) -> set[str]:
        # All branches belonging to one connector component form a legitimate
        # junction. They must not warn about the small, intentional overlap at
        # the shared point, even when two branches are linked through a third
        # element rather than by their own TrackConnection record.
        junctions: list[set[ConnectorRef]] = []
        for connection in self.project.connections:
            matching = [group for group in junctions
                        if connection.first in group or connection.second in group]
            if not matching:
                junctions.append({connection.first, connection.second})
                continue
            combined = {connection.first, connection.second}
            for group in matching:
                combined.update(group)
                junctions.remove(group)
            junctions.append(combined)
        connected_pairs: set[frozenset[str]] = set()
        for junction in junctions:
            element_ids = {connector.element_id for connector in junction}
            for first_id in element_ids:
                for second_id in element_ids:
                    if first_id != second_id:
                        connected_pairs.add(frozenset((first_id, second_id)))
        overlaps: set[str] = set()
        for index, first in enumerate(self.project.elements):
            first_shape = self._road_shape(first)
            for second in self.project.elements[index + 1:]:
                if frozenset((first.id, second.id)) in connected_pairs:
                    continue
                if self._shapes_overlap(first_shape, self._road_shape(second)):
                    overlaps.update((first.id, second.id))
        return overlaps

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
        moving_ids = self.selected_ids | self._drag_joint_followers
        elements = [item for item in self.project.elements if item.id in moving_ids]
        dx, dy = self.project.clamp_group_translation(elements, dx, dy)
        if abs(dx) <= 1e-12 and abs(dy) <= 1e-12: return 0.0, 0.0
        for item in elements: item.moved(dx, dy)
        for element_id, (hinge, _fixed, fixed_point) in self._drag_joint_bridges.items():
            element = self.project.element_by_id(element_id)
            if element is None:
                continue
            hinge_connection = self.project.connection_for(hinge)
            if hinge_connection is None:
                continue
            anchor = (hinge_connection.second if hinge_connection.first == hinge
                      else hinge_connection.first)
            hinge_point = self.project.connector_pose(anchor).point
            self._reshape_straight_between_joints(
                element, hinge.endpoint, hinge_point, fixed_point
            )
        return dx, dy

    @staticmethod
    def _reshape_straight_between_joints(element: TrackElement, hinge_endpoint: str,
                                         hinge_point: Point, fixed_point: Point) -> None:
        if hinge_endpoint == "start":
            element.start = hinge_point
            element.heading_deg = degrees(atan2(
                fixed_point.y - hinge_point.y,
                fixed_point.x - hinge_point.x,
            )) % 360
        else:
            element.start = fixed_point
            element.heading_deg = degrees(atan2(
                hinge_point.y - fixed_point.y,
                hinge_point.x - fixed_point.x,
            )) % 360
        element.length = max(0.05, hypot(
            fixed_point.x - hinge_point.x,
            fixed_point.y - hinge_point.y,
        ))

    def _junction_connectors(self, connector: ConnectorRef) -> set[ConnectorRef]:
        result = {connector}
        pending = [connector]
        while pending:
            current = pending.pop()
            for connection in self.project.connections_for(current):
                peer = connection.second if connection.first == current else connection.first
                if peer not in result:
                    result.add(peer)
                    pending.append(peer)
        return result

    def _move_boundary_junction_to(self, connector: ConnectorRef, point: Point) -> bool:
        junction = self._junction_connectors(connector)
        if len(junction) < 2:
            return False
        originals: dict[str, TrackElement] = {}
        for member in junction:
            element = self.project.element_by_id(member.element_id)
            if (element is None or element.element_type != "boundary"
                    or member.endpoint not in {"start", "end"}
                    or element.id in originals):
                continue
            originals[element.id] = deepcopy(element)
            other_endpoint = "end" if member.endpoint == "start" else "start"
            fixed_point = element.pose_at(other_endpoint).point
            if element.kind == "straight":
                self._reshape_straight_between_joints(
                    element, member.endpoint, point, fixed_point
                )
            else:
                start = point if member.endpoint == "start" else fixed_point
                end = fixed_point if member.endpoint == "start" else point
                chord = hypot(end.x - start.x, end.y - start.y)
                half_angle = radians(abs(element.signed_angle_deg) / 2)
                if chord <= 1e-6 or abs(sin(half_angle)) <= 1e-9:
                    for element_id, original in originals.items():
                        self._restore_element_geometry(
                            self.project.element_by_id(element_id), original
                        )
                    return False
                radius = chord / (2 * sin(half_angle))
                if radius < element.minimum_centerline_radius:
                    for element_id, original in originals.items():
                        self._restore_element_geometry(
                            self.project.element_by_id(element_id), original
                        )
                    return False
                bearing = degrees(atan2(end.y - start.y, end.x - start.x))
                element.start = start
                element.heading_deg = (bearing - element.signed_angle_deg / 2) % 360
                element.radius = radius
        if not all(self.project.element_fits_hall(self.project.element_by_id(element_id))
                   for element_id in originals):
            for element_id, original in originals.items():
                self._restore_element_geometry(
                    self.project.element_by_id(element_id), original
                )
            return False
        return bool(originals)

    @staticmethod
    def _restore_element_geometry(element: TrackElement, before: TrackElement) -> None:
        element.start = before.start
        element.heading_deg = before.heading_deg
        element.length = before.length
        element.radius = before.radius
        element.angle_deg = before.angle_deg
        element.rotation_reference_deg = before.rotation_reference_deg

    def _resize_free_connector_to(self, connector: ConnectorRef, point: Point,
                                  snap_values: bool = True) -> bool:
        element = self.project.element_by_id(connector.element_id)
        if element is None or not self.project.is_free(connector):
            return False
        fixed_endpoint = "end" if connector.endpoint == "start" else "start"
        fixed_connector = ConnectorRef(element.id, fixed_endpoint)
        fixed_connection = self.project.connection_for(fixed_connector)
        freely_resizable_boundary = (element.element_type == "boundary"
                                     and element.kind == "straight")
        if (fixed_connection is None
                and not freely_resizable_boundary):
            return False
        fixed_pose = element.pose_at(fixed_endpoint)
        before = deepcopy(element)
        if element.kind == "straight":
            if element.element_type == "boundary" and fixed_connection is not None:
                # A one-sided connected boundary acts like a telescopic lever:
                # the connected endpoint is the pivot while the mouse controls
                # both its heading and its continuously variable length.
                dx = point.x - fixed_pose.point.x
                dy = point.y - fixed_pose.point.y
                length = hypot(dx, dy)
                if not 0.1 <= length <= 200:
                    return False
                direction = degrees(atan2(dy, dx))
                element.length = length
                element.heading_deg = (direction + (180 if fixed_endpoint == "end" else 0)) % 360
                if fixed_endpoint == "start":
                    element.start = fixed_pose.point
                else:
                    current_end = element.end_pose.point
                    element.start = Point(
                        element.start.x + fixed_pose.point.x - current_end.x,
                        element.start.y + fixed_pose.point.y - current_end.y,
                    )
                element.rotation_reference_deg = element.heading_deg
            else:
                direction = fixed_pose.heading_deg + (180 if fixed_endpoint == "end" else 0)
                angle = radians(direction)
                length = ((point.x - fixed_pose.point.x) * cos(angle)
                          + (point.y - fixed_pose.point.y) * sin(angle))
                if snap_values and element.element_type != "boundary":
                    length = round(length * 2) / 2
                if length < 0.1 or length > 200:
                    return False
                element.length = length
                element.align_endpoint(fixed_endpoint, fixed_pose)
        else:
            backwards = fixed_endpoint == "end"
            direction = fixed_pose.heading_deg + (180 if backwards else 0)
            effective_turn = (1 if element.kind == "left" else -1) * (-1 if backwards else 1)
            angle = radians(direction)
            dx, dy = point.x - fixed_pose.point.x, point.y - fixed_pose.point.y
            forward = dx * cos(angle) + dy * sin(angle)
            left = -dx * sin(angle) + dy * cos(angle)
            lateral = left * effective_turn
            curve_angle = degrees(2 * atan2(lateral, forward))
            if not 1 <= curve_angle <= 90:
                return False
            chord = hypot(dx, dy)
            radius = chord / (2 * sin(radians(curve_angle / 2)))
            if snap_values:
                radius = round(radius * 2) / 2
                curve_angle = round(curve_angle / 5) * 5
            if (not element.minimum_centerline_radius <= radius <= 200
                    or not 1 <= curve_angle <= 90):
                return False
            element.radius = radius
            element.angle_deg = curve_angle
            element.align_endpoint(fixed_endpoint, fixed_pose)
        if not self.project.element_fits_hall(element):
            self._restore_element_geometry(element, before)
            return False
        return True

    def _finish_connector_resize(self, release_position: QPointF | None = None) -> None:
        connector = self._resize_connector
        if connector is None or not self._resize_started:
            return
        element = self.project.element_by_id(connector.element_id)
        candidate = self._find_snap(element) if element else None
        if release_position is not None:
            direct_target = self._free_connector_at_excluding(
                release_position, connector, self._current_snap_distance()
            )
            if direct_target:
                aligned_target = self.project.connector_alignment_pose(
                    connector, direct_target
                )
                candidate = (0.0, connector, direct_target,
                             aligned_target)
        connected = False
        if candidate and candidate[1] == connector:
            _score, own, other, target = candidate
            before_fit = deepcopy(element)
            if self._resize_free_connector_to(connector, target.point, snap_values=False):
                own_pose = element.pose_at(connector.endpoint)
                distance = hypot(own_pose.point.x - target.point.x,
                                 own_pose.point.y - target.point.y)
                angle = self._angle_difference(own_pose.heading_deg, target.heading_deg)
                if (distance <= 1e-6
                        and (element.element_type == "boundary" or angle <= 1e-6)):
                    self.project.connect(own, other)
                    connected = True
                else:
                    self._restore_element_geometry(element, before_fit)
        if connected:
            self.active_connector = None
            self.status_message.emit(self._tr("Element snapped into place."))
        else:
            self.active_connector = connector
        self._commit_change(self._tr("Resize element"), self._resize_before,
                            self._resize_before_selection, self._resize_before_connector)

    def _hit_test(self, pos: QPointF) -> TrackElement | None:
        candidates: list[tuple[float, int, TrackElement]] = []
        for order, element in enumerate(self.project.elements):
            distance = self._distance_to_centerline(pos, element)
            tolerance = max(5.0, element.width * self.scale / 2 + 4.0)
            if distance <= tolerance:
                # Keep the current selection stable only when two centerlines
                # are effectively the same distance from the click.
                selection_priority = 0 if element.id in self.selected_ids else 1
                candidates.append((distance, selection_priority, element))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (round(item[0], 3), item[1]))
        return candidates[0][2]

    def _distance_to_centerline(self, pos: QPointF, element: TrackElement) -> float:
        points = [self.world_to_screen(point)
                  for point in element.centerline_points(maximum_step_deg=2.0)]
        best = float("inf")
        for start, end in zip(points, points[1:]):
            dx, dy = end.x() - start.x(), end.y() - start.y()
            length_squared = dx * dx + dy * dy
            if length_squared <= 1e-12:
                distance = hypot(pos.x() - start.x(), pos.y() - start.y())
            else:
                factor = max(0.0, min(1.0, (
                    (pos.x() - start.x()) * dx + (pos.y() - start.y()) * dy
                ) / length_squared))
                nearest_x = start.x() + factor * dx
                nearest_y = start.y() + factor * dy
                distance = hypot(pos.x() - nearest_x, pos.y() - nearest_y)
            best = min(best, distance)
        return best

    @staticmethod
    def _snap_guide(value: float) -> float:
        return round(value * 2) / 2

    def _guide_at(self, pos: QPointF) -> tuple[str, int, float] | None:
        hall = QRectF(self.pan.x(), self.pan.y(), self.project.hall_length * self.scale,
                      self.project.hall_width * self.scale)
        if not hall.adjusted(-6, -6, 6, 6).contains(pos):
            return None
        best = None
        for index, value in enumerate(self.project.guides_x):
            distance = abs(self.world_to_screen(Point(value, 0)).x() - pos.x())
            if distance <= 6 and (best is None or distance < best[0]):
                best = (distance, "x", index, value)
        for index, value in enumerate(self.project.guides_y):
            distance = abs(self.world_to_screen(Point(0, value)).y() - pos.y())
            if distance <= 6 and (best is None or distance < best[0]):
                best = (distance, "y", index, value)
        return None if best is None else (best[1], best[2], best[3])

    def _start_guide_drag(self, axis: str, value: float,
                          existing: tuple[str, int, float] | None = None) -> None:
        self._guide_drag_axis = axis
        self._guide_drag_value = value
        self._guide_drag_existing = existing
        self._guide_drag_before = deepcopy(self.project)
        self.setCursor(Qt.CursorShape.SizeHorCursor if axis == "x" else Qt.CursorShape.SizeVerCursor)
        self.update()

    def _draw_rulers(self, painter: QPainter, area: QRectF, grid: float) -> None:
        ruler = self._ruler_size
        ruler_color = QColor(self._colors["canvas"])
        text_color = QColor(self._colors["text"])
        border_color = QColor("#111111")
        top = QRectF(area.left(), area.top() - ruler, area.width(), ruler)
        left = QRectF(area.left() - ruler, area.top(), ruler, area.height())
        painter.fillRect(top, ruler_color); painter.fillRect(left, ruler_color)
        painter.setPen(QPen(border_color, 1)); painter.drawRect(top); painter.drawRect(left)
        label_step = 1 if self.scale >= 38 else 2 if self.scale >= 18 else 5 if self.scale >= 8 else 10
        painter.setPen(text_color)
        x = 0.0
        while x <= self.project.hall_length + 1e-9:
            sx = self.world_to_screen(Point(x, 0)).x()
            painter.drawLine(QPointF(sx, area.top() - 6), QPointF(sx, area.top()))
            if abs((x / label_step) - round(x / label_step)) < 1e-9:
                if abs(x) < 1e-9:
                    label_rect = QRectF(sx + 2, top.top(), 38, ruler - 7)
                    alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                elif abs(x - self.project.hall_length) < 1e-9:
                    label_rect = QRectF(sx - 40, top.top(), 38, ruler - 7)
                    alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                else:
                    label_rect = QRectF(sx - 20, top.top(), 40, ruler - 7)
                    alignment = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                painter.drawText(label_rect, alignment, f"{x:g}")
            x += grid
        y = 0.0
        while y <= self.project.hall_width + 1e-9:
            sy = self.world_to_screen(Point(0, y)).y()
            painter.drawLine(QPointF(area.left() - 6, sy), QPointF(area.left(), sy))
            # The upper value would collide with the X-axis zero at the shared
            # ruler corner. The area size above the ruler already provides it.
            if (abs(y - self.project.hall_width) > 1e-9
                    and abs((y / label_step) - round(y / label_step)) < 1e-9):
                label_top = sy - 18 if abs(y) < 1e-9 else sy - 9
                painter.drawText(QRectF(left.left(), label_top, ruler - 7, 18),
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                 f"{y:g}")
            y += grid

    def _draw_guides(self, painter: QPainter, area: QRectF) -> None:
        painter.save(); painter.setClipRect(area)
        guide_color = QColor("#d000a8")
        guide_color.setAlpha(145)
        painter.setPen(QPen(guide_color, 1, Qt.PenStyle.SolidLine))
        skip = self._guide_drag_existing
        for index, value in enumerate(self.project.guides_x):
            if skip and skip[0] == "x" and skip[1] == index: continue
            sx = self.world_to_screen(Point(value, 0)).x()
            painter.drawLine(QPointF(sx, area.top()), QPointF(sx, area.bottom()))
        for index, value in enumerate(self.project.guides_y):
            if skip and skip[0] == "y" and skip[1] == index: continue
            sy = self.world_to_screen(Point(0, value)).y()
            painter.drawLine(QPointF(area.left(), sy), QPointF(area.right(), sy))
        if self._guide_drag_axis and self._guide_drag_value is not None:
            if self._guide_drag_axis == "x":
                sx = self.world_to_screen(Point(self._guide_drag_value, 0)).x()
                painter.drawLine(QPointF(sx, area.top()), QPointF(sx, area.bottom()))
            else:
                sy = self.world_to_screen(Point(0, self._guide_drag_value)).y()
                painter.drawLine(QPointF(area.left(), sy), QPointF(area.right(), sy))
        painter.restore()

    def _draw_area_caption(self, painter: QPainter, grid: float) -> None:
        text = (f"{self._tr('Track area')}  {self.project.hall_length:g} m × "
                f"{self.project.hall_width:g} m  |  {self._tr('Grid {grid} m', grid=grid)}")
        if self.project_name:
            text += f"  |  {self.project_name}"
        width = self.fontMetrics().horizontalAdvance(text) + 14
        caption = QRectF(8, 6, width, 24)
        background = QColor(self._colors["canvas"])
        background.setAlpha(225)
        painter.fillRect(caption, background)
        painter.setPen(QColor(self._colors["text"]))
        painter.drawText(caption.adjusted(6, 0, -4, 0),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         text)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self._colors["canvas"]))
        hall = QRectF(self.pan.x(), self.pan.y(), self.project.hall_length * self.scale,
                      self.project.hall_width * self.scale)
        indoor = self.project.editor_mode == "indoor"
        painter.fillRect(hall, QColor("#34383E" if indoor else self._colors["hall"]))
        painter.save()
        painter.setClipRect(hall)
        grid = 1 if self.scale >= 12 else 5
        grid_color = QColor("#FFFFFF" if indoor else self._colors["grid"])
        if indoor:
            grid_color.setAlpha(48)
        painter.setPen(QPen(grid_color, 1))
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
            painter.setBrush(QColor("#F4CC2E" if element.element_type == "boundary"
                                    else self._colors["track"]))
            painter.drawPath(self._road_shape(element))
        # A very shallow tangent-aligned bridge removes antialiasing hairlines
        # without creating a round bulge on short curve segments.
        painter.setPen(Qt.PenStyle.NoPen)
        for connection in self.project.connections:
            first = self.project.element_by_id(connection.first.element_id)
            painter.setBrush(QColor("#F4CC2E" if first.element_type == "boundary"
                                    else self._colors["track"]))
            painter.drawPolygon(connection_bridge_polygon(
                self.project,
                connection,
                self.world_to_screen,
                self.scale,
                half_depth=1.5,
            ))
        # Outline the actual road contour instead of drawing a second, wider
        # road underneath it. The old halo produced wedges and uneven caps on
        # selected 75°–90° curves.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#ffb020"), 3, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for element in self.project.elements:
            if element.id in self.selected_ids:
                painter.drawPath(self._road_shape(element))
        overlapping_ids = self.overlapping_element_ids()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#ffffff"), 4, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.RoundJoin))
        for element in self.project.elements:
            if element.id in overlapping_ids:
                painter.drawPath(self._road_shape(element))
        painter.setPen(QPen(QColor("#e1262f"), 4, Qt.PenStyle.DashLine,
                            Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.RoundJoin))
        for element in self.project.elements:
            if element.id in overlapping_ids:
                painter.drawPath(self._road_shape(element))
        for element in self.project.elements:
            if element.element_type == "boundary":
                continue
            painter.setPen(QPen(QColor(self._colors["centerline"]), 1, Qt.PenStyle.DashLine))
            painter.drawPath(self._element_path(element))
        for item in self.project.planning_objects:
            draw_planning_object(
                painter, item, self.world_to_screen, self.scale,
                selected=item is self.selected_planning,
                number=self.project.starting_grid_number(item),
                label=self._tr("Drivers' Stand") if item.kind == "drivers_stand" else None,
            )
        if self.selected_planning and self.selected_planning.kind not in {"starting_grid", "drivers_stand"}:
            painter.setPen(QPen(QColor("#101214"), 1))
            painter.setBrush(QColor("#31a8ff"))
            for endpoint in self.selected_planning.endpoints:
                painter.drawEllipse(self.world_to_screen(endpoint), 4, 4)
        if (self.selected_planning and self.selected_planning.kind == "drivers_stand"
                and not self.selected_planning.locked):
            painter.setPen(QPen(QColor("#101214"), 1))
            painter.setBrush(QColor("#31a8ff"))
            for point in drivers_stand_handles(self.selected_planning).values():
                screen = self.world_to_screen(point)
                painter.drawRect(QRectF(screen.x() - 4, screen.y() - 4, 8, 8))
        if self.snap_preview:
            painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QColor("#ffad24"), 3))
            for connector in self.snap_preview:
                point = self.world_to_screen(self.project.connector_pose(connector).point)
                painter.drawEllipse(point, 10, 10)
        if self.planning_snap_preview is not None:
            point = self.world_to_screen(self.planning_snap_preview)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#ffad24"), 3))
            painter.drawEllipse(point, 9, 9)
        for element in self.project.elements:
            for endpoint in element.connector_names:
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
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#d000a8"), 3))
        for connector in self.closure_connectors:
            if self.project.element_by_id(connector.element_id):
                point = self.world_to_screen(self.project.connector_pose(connector).point)
                painter.drawEllipse(point, 8, 8)
        if self.selected and len(self.selected_ids) <= 1:
            pivot = self.world_to_screen(self.selected.centerline_midpoint)
            painter.setBrush(QColor(self._colors["canvas"]))
            painter.setPen(QPen(QColor("#ffad24"), 1))
            painter.drawEllipse(pivot, 3.5, 3.5)
            painter.drawLine(pivot + QPointF(-6, 0), pivot + QPointF(6, 0))
            painter.drawLine(pivot + QPointF(0, -6), pivot + QPointF(0, 6))
        self._draw_guides(painter, hall)
        if self.planning_placement and self.planning_draft_start is not None:
            start = self.world_to_screen(self.planning_draft_start)
            end = self.world_to_screen(
                self.planning_draft_preview or self.planning_draft_start
            )
            painter.setPen(QPen(QColor("#ffcc20"), 3, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.setBrush(QColor("#ffcc20"))
            painter.drawLine(start, end)
            painter.drawEllipse(start, 4, 4)
            painter.drawEllipse(end, 4, 4)
        self._draw_measurement(painter)
        painter.restore()
        painter.setPen(QPen(QColor("#111111"), 2))
        painter.drawRect(hall)
        self._draw_rulers(painter, hall, grid)
        self._draw_area_caption(painter, grid)

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
        position = event.position()
        hall = QRectF(self.pan.x(), self.pan.y(), self.project.hall_length * self.scale,
                      self.project.hall_width * self.scale)
        if self.measurement.active:
            if hall.contains(position) and self.measurement.end is None:
                self._set_measurement_point(position)
            return
        if self.planning_placement:
            if hall.contains(position):
                kind, length = self.planning_placement
                world = self.screen_to_world(position)
                if kind in {"starting_grid", "drivers_stand"}:
                    before = deepcopy(self.project)
                    before_selection = self._selection_state()
                    item = PlanningObject(
                        kind, world,
                        length=4.0 if kind == "drivers_stand" else 0.5,
                        width=1.0 if kind == "drivers_stand" else 0.2,
                    )
                    if not item.fits_hall(
                        self.project.hall_length, self.project.hall_width
                    ):
                        self.status_message.emit(self._tr(
                            "The object would extend beyond the track area."
                        ))
                        return
                    self.project.planning_objects.append(item)
                    self.selected = None
                    self.selected_planning = item
                    self.selected_ids.clear()
                    self.planning_placement = None
                    self.unsetCursor()
                    self._commit_change(
                        self._tr("Place drivers' stand" if kind == "drivers_stand"
                                 else "Place starting grid position"), before,
                        before_selection, None,
                    )
                    return
                if self.planning_draft_start is None:
                    straight = self._hit_test(position)
                    if kind == "start_finish" and straight and straight.kind == "straight":
                        snap_point = self._planning_snap_point(world)
                        self.planning_draft_start = snap_point or world
                        self.planning_draft_axis_deg = (straight.heading_deg + 90) % 360
                    else:
                        self.planning_draft_start = world
                        self.planning_draft_axis_deg = None
                    self.planning_draft_preview = self.planning_draft_start
                    self.status_message.emit(self._tr(
                        "Click the second point to set marker length and direction."
                    ))
                    self.update()
                    return
                snap_point = self._planning_snap_point(world)
                self.planning_snap_preview = snap_point
                world = snap_point or world
                world = self._constrain_planning_draft(world)
                dx = world.x - self.planning_draft_start.x
                dy = world.y - self.planning_draft_start.y
                measured_length = hypot(dx, dy)
                if measured_length < 0.05:
                    self.status_message.emit(self._tr(
                        "The marker must be at least 0.05 m long."
                    ))
                    return
                before = deepcopy(self.project)
                before_selection = self._selection_state()
                center = Point(
                    (self.planning_draft_start.x + world.x) / 2,
                    (self.planning_draft_start.y + world.y) / 2,
                )
                item = PlanningObject(
                    kind,
                    center,
                    length=measured_length,
                    heading_deg=(degrees(atan2(dy, dx)) - 90) % 360,
                )
                self._snap_planning_to_straight(item)
                if not item.fits_hall(self.project.hall_length, self.project.hall_width):
                    self.status_message.emit(self._tr("The object would extend beyond the track area."))
                    return
                self.project.planning_objects.append(item)
                self.selected = None
                self.selected_planning = item
                self.selected_ids.clear()
                self.planning_placement = None
                self.planning_draft_start = None
                self.planning_draft_preview = None
                self.planning_draft_axis_deg = None
                self.planning_snap_preview = None
                self.unsetCursor()
                self._commit_change(self._tr("Place marker"), before, before_selection, None)
            return
        side_handle = self._drivers_stand_handle_at(position)
        if side_handle and self.selected_planning:
            handles = drivers_stand_handles(self.selected_planning)
            opposite = {"left": "right", "right": "left",
                        "top": "bottom", "bottom": "top"}[side_handle]
            self._planning_side_handle = side_handle
            self._planning_side_fixed = handles[opposite]
            self._planning_side_before = deepcopy(self.project)
            return
        planning_endpoint = self._planning_endpoint_at(position)
        if planning_endpoint:
            planning_item, endpoint_index = planning_endpoint
            self.selected = None
            self.selected_planning = planning_item
            self.selected_ids.clear()
            self.active_connector = None
            self.selection_changed.emit(planning_item)
            if not planning_item.locked:
                self._planning_resize_endpoint = endpoint_index
                self._planning_resize_fixed = planning_item.endpoints[1 - endpoint_index]
                self._planning_resize_before = deepcopy(self.project)
            self.update()
            return
        planning_item = self._planning_at(position)
        if planning_item:
            self.selected = None
            self.selected_planning = planning_item
            self.selected_ids.clear()
            self.active_connector = None
            self._dragging_planning = not planning_item.locked
            self._planning_drag_before = deepcopy(self.project)
            pointer = self.screen_to_world(position)
            self._planning_drag_offset = Point(
                planning_item.center.x - pointer.x,
                planning_item.center.y - pointer.y,
            )
            self.selection_changed.emit(planning_item)
            self.update()
            return
        if not self.placement:
            existing_guide = self._guide_at(position)
            if existing_guide:
                self._start_guide_drag(existing_guide[0], existing_guide[2], existing_guide)
                return
        top_ruler = QRectF(hall.left(), hall.top() - self._ruler_size, hall.width(), self._ruler_size)
        left_ruler = QRectF(hall.left() - self._ruler_size, hall.top(), self._ruler_size, hall.height())
        if top_ruler.contains(position):
            value = min(self.project.hall_length, max(0.0, self._snap_guide(self.screen_to_world(position).x)))
            self._start_guide_drag("x", value)
            return
        if left_ruler.contains(position):
            value = min(self.project.hall_width, max(0.0, self._snap_guide(self.screen_to_world(position).y)))
            self._start_guide_drag("y", value)
            return
        world = self.screen_to_world(event.position())
        if self.placement:
            connector = self._connector_at(event.position(), free_only=True)
            wanted_type = "boundary" if self.project.editor_mode == "indoor" else "track"
            if (connector and self.project.element_by_id(connector.element_id).element_type
                    != wanted_type):
                connector = None
            if connector:
                self.active_connector = connector
                kind, angle = self.placement
                self.placement = None; self.unsetCursor()
                self._append_to_active(kind, angle or 45.0)
                return
            kind, angle = self.placement
            if 0 <= world.x <= self.project.hall_length and 0 <= world.y <= self.project.hall_width:
                before = deepcopy(self.project); before_connector = self.active_connector; before_selection = self._selection_state()
                element_kind = "left" if kind == "curve" else kind
                element = TrackElement(element_kind, world, width=self.default_width, length=self.default_length,
                                       radius=self.default_radius, angle_deg=angle or 45.0,
                                       element_type=("boundary" if self.project.editor_mode == "indoor" else "track"))
                if not self.project.element_fits_hall(element):
                    self.status_message.emit(self._tr("The element would extend beyond the track area."))
                    return
                self.project.elements.append(element)
                self.selected = element; self.selected_ids = {element.id}
                self.active_connector = ConnectorRef(element.id, "end")
                self.placement = None
                self.unsetCursor()
                self._commit_change(self._tr("Place element"), before, before_selection, before_connector)
            return
        connector = self._connector_at(event.position())
        if connector:
            if (connector.endpoint in {"start", "end"}
                    and event.modifiers() & Qt.KeyboardModifier.ControlModifier
                    and self.project.is_free(connector)):
                self.toggle_closure_connector(connector)
                return
            element = self.project.element_by_id(connector.element_id)
            self.selected = element
            self.selected_ids = {element.id}
            self.active_connector = (connector if self.project.can_accept_connection(connector)
                                     else None)
            if (self.project.editor_mode == "indoor"
                    and element.element_type == "boundary"
                    and connector.endpoint in {"start", "end"}
                    and self.project.connections_for(connector)):
                self._junction_drag_connector = connector
                self._junction_drag_started = False
                self._junction_drag_before = deepcopy(self.project)
                self._junction_drag_before_selection = self._selection_state()
                self._junction_drag_before_connector = self.active_connector
            elif (connector.endpoint.startswith("magnet:")
                    and element.element_type == "boundary"
                    and element.kind == "straight"):
                self._magnet_drag_connector = connector
                self._magnet_drag_started = False
                self._magnet_drag_before = deepcopy(self.project)
                self._magnet_drag_before_selection = self._selection_state()
                self._magnet_drag_before_connector = self.active_connector
            other_endpoint = "end" if connector.endpoint == "start" else "start"
            if (self._junction_drag_connector is None
                    and connector.endpoint in {"start", "end"}
                    and self.active_connector
                    and (self.project.connection_for(ConnectorRef(element.id, other_endpoint))
                         or (element.element_type == "boundary"
                             and element.kind == "straight"))):
                self._resize_connector = connector
                self._resize_started = False
                self._resize_before = deepcopy(self.project)
                self._resize_before_selection = self._selection_state()
                self._resize_before_connector = self.active_connector
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
            self.selected_planning = None
            self.selection_changed.emit(None)
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
        if self.measurement.active:
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            connector = self._connector_at(event.position())
            if connector and self.project.connection_for(connector):
                self.disconnect_connector(connector)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def _delete_guide(self, guide: tuple[str, int, float]) -> None:
        axis, index, _value = guide
        before = deepcopy(self.project)
        before_selection = self._selection_state()
        before_connector = self.active_connector
        values = self.project.guides_x if axis == "x" else self.project.guides_y
        values.pop(index)
        self._commit_change(self._tr("Delete guide"), before,
                            before_selection, before_connector)

    def _magnet_insertion_at(self, pos: QPointF,
                             element: TrackElement | None) -> tuple[TrackElement, float] | None:
        if (self.project.editor_mode != "indoor" or element is None
                or element.element_type != "boundary" or element.kind != "straight"):
            return None
        start = self.world_to_screen(element.start)
        end = self.world_to_screen(element.end_pose.point)
        dx, dy = end.x() - start.x(), end.y() - start.y()
        length_squared = dx * dx + dy * dy
        if length_squared <= 1e-9:
            return None
        fraction = ((pos.x() - start.x()) * dx + (pos.y() - start.y()) * dy) / length_squared
        if not 0.03 < fraction < 0.97:
            return None
        nearest = QPointF(start.x() + fraction * dx, start.y() + fraction * dy)
        tolerance = max(6.0, element.width * self.scale / 2 + 4.0)
        if hypot(pos.x() - nearest.x(), pos.y() - nearest.y()) > tolerance:
            return None
        return element, fraction

    def add_magnet_point(self, element: TrackElement, fraction: float) -> ConnectorRef:
        if (self.project.editor_mode != "indoor" or element.element_type != "boundary"
                or element.kind != "straight" or not 0.0 < fraction < 1.0):
            raise ValueError("Magnet points can only be added to straight boundaries")
        before = deepcopy(self.project)
        before_selection = self._selection_state()
        before_connector = self.active_connector
        point_id = str(uuid4())
        element.magnet_points[point_id] = fraction
        connector = ConnectorRef(element.id, f"magnet:{point_id}")
        self.selected = element
        self.selected_ids = {element.id}
        self.active_connector = connector
        self._commit_change(self._tr("Add magnet point"), before,
                            before_selection, before_connector)
        return connector

    def remove_magnet_point(self, connector: ConnectorRef) -> bool:
        if not connector.endpoint.startswith("magnet:"):
            return False
        element = self.project.element_by_id(connector.element_id)
        point_id = connector.endpoint.split(":", 1)[1]
        if element is None or point_id not in element.magnet_points:
            return False
        before = deepcopy(self.project)
        before_selection = self._selection_state()
        before_connector = self.active_connector
        self.project.disconnect_all(connector)
        del element.magnet_points[point_id]
        self.selected = element
        self.selected_ids = {element.id}
        if self.active_connector == connector:
            self.active_connector = None
        self._commit_change(self._tr("Remove magnet point"), before,
                            before_selection, before_connector)
        return True

    def _directly_attached_connectors(self, connector: ConnectorRef) -> list[ConnectorRef]:
        """Return every element connector attached to a custom magnet point."""
        return [
            connection.second if connection.first == connector else connection.first
            for connection in self.project.connections_for(connector)
        ]

    def _move_magnet_point_to(self, connector: ConnectorRef, position: QPointF) -> bool:
        element = self.project.element_by_id(connector.element_id)
        if (element is None or element.element_type != "boundary"
                or element.kind != "straight"
                or not connector.endpoint.startswith("magnet:")):
            return False
        start = self.world_to_screen(element.start)
        end = self.world_to_screen(element.end_pose.point)
        dx, dy = end.x() - start.x(), end.y() - start.y()
        length_squared = dx * dx + dy * dy
        if length_squared <= 1e-9:
            return False
        fraction = ((position.x() - start.x()) * dx
                    + (position.y() - start.y()) * dy) / length_squared
        fraction = min(0.97, max(0.03, fraction))
        old_point = element.pose_at(connector.endpoint).point
        point_id = connector.endpoint.split(":", 1)[1]
        element.magnet_points[point_id] = fraction
        new_point = element.pose_at(connector.endpoint).point
        move_x, move_y = new_point.x - old_point.x, new_point.y - old_point.y
        for peer in self._directly_attached_connectors(connector):
            attached_id = peer.element_id
            attached = self.project.element_by_id(attached_id)
            other_endpoint = ("end" if peer.endpoint == "start" else "start")
            other_connector = (ConnectorRef(attached_id, other_endpoint)
                               if peer.endpoint in {"start", "end"} else None)
            other_connection = (self.project.connection_for(other_connector)
                                if other_connector else None)
            if (attached is not None and attached.kind == "straight"
                    and attached.element_type == "boundary"
                    and other_connection is not None):
                fixed_point = attached.pose_at(other_endpoint).point
                self._reshape_straight_between_joints(
                    attached, peer.endpoint, new_point, fixed_point
                )
            elif attached is not None:
                attached.start = Point(attached.start.x + move_x,
                                       attached.start.y + move_y)
        return True

    def _build_context_menu(self, connector: ConnectorRef | None,
                            guide: tuple[str, int, float] | None,
                            can_delete: bool = False,
                            magnet_candidate: tuple[TrackElement, float] | None = None) -> QMenu | None:
        connection = self.project.connection_for(connector) if connector else None
        removable_magnet = bool(connector and connector.endpoint.startswith("magnet:"))
        can_close = len(self.closure_connectors) == 2
        if not (connection or guide or can_close or can_delete
                or magnet_candidate or removable_magnet):
            return None
        menu = QMenu(self)
        if removable_magnet and connector:
            action = menu.addAction(self._tr("Remove magnet point"))
            action.triggered.connect(
                lambda checked=False, selected=connector:
                self.remove_magnet_point(selected)
            )
        elif magnet_candidate:
            element, fraction = magnet_candidate
            action = menu.addAction(self._tr("Add magnet point"))
            action.triggered.connect(
                lambda checked=False, selected=element, position=fraction:
                self.add_magnet_point(selected, position)
            )
        if can_close:
            action = menu.addAction(self._tr("Close track…"))
            action.triggered.connect(self.close_track_requested.emit)
        if connection and connector:
            action = menu.addAction(self._tr("Disconnect connection"))
            action.triggered.connect(
                lambda checked=False, selected=connector:
                self.disconnect_connector(selected)
            )
        if guide:
            action = menu.addAction(self._tr("Delete guide"))
            action.triggered.connect(
                lambda checked=False, selected=guide: self._delete_guide(selected)
            )
        if can_delete:
            if menu.actions():
                menu.addSeparator()
            action = menu.addAction(self._tr("Delete selection"))
            action.triggered.connect(self.delete_selected)
        return menu

    def _build_measurement_context_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction(self._tr("Clear measurement"), self.clear_measurement)
        menu.addAction(self._tr("Exit measurement"), self.exit_measurement)
        return menu

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        if self.measurement.active:
            self._build_measurement_context_menu().exec(event.globalPos())
            event.accept()
            return
        planning_item = self._planning_at(QPointF(event.pos()))
        if planning_item:
            self.selected = None
            self.selected_planning = planning_item
            self.selected_ids.clear()
            self.selection_changed.emit(planning_item)
            menu = QMenu(self)
            menu.addAction(
                self._tr("Unlock" if planning_item.locked else "Lock"),
                self.toggle_selected_planning_lock,
            )
            menu.addAction(self._tr("Delete marker"), self.delete_selected)
            menu.exec(event.globalPos())
            event.accept()
            return
        connector = self._connector_at(event.pos())
        guide = self._guide_at(QPointF(event.pos()))
        connection = self.project.connection_for(connector) if connector else None
        clicked = (self.project.element_by_id(connector.element_id)
                   if connector else self._hit_test(QPointF(event.pos())))
        magnet_candidate = (None if connector and connector.endpoint.startswith("magnet:")
                            else self._magnet_insertion_at(QPointF(event.pos()), clicked))
        if clicked and clicked.id not in self.selected_ids:
            self.selected = clicked
            self.selected_ids = {clicked.id}
            self.active_connector = (connector if connector
                                     and self.project.can_accept_connection(connector)
                                     else None)
            self.selection_changed.emit(clicked)
            self.update()
        can_delete = bool(clicked and clicked.id in self.selected_ids)
        if guide and not connection and len(self.closure_connectors) != 2:
            self._delete_guide(guide)
            event.accept()
            return
        menu = self._build_context_menu(connector, guide, can_delete, magnet_candidate)
        if menu:
            menu.exec(event.globalPos())
            event.accept()
            return
        super().contextMenuEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        delta = event.position().toPoint() - self._last_mouse
        self._last_mouse = event.position().toPoint()
        if self._panning:
            self.pan += QPointF(delta)
            self.update()
        elif (self._planning_side_handle and self.selected_planning
              and self._planning_side_fixed is not None):
            item = self.selected_planning
            world = self.screen_to_world(event.position())
            angle = radians(item.heading_deg)
            along = Point(cos(angle), sin(angle))
            across = Point(-sin(angle), cos(angle))
            fixed = self._planning_side_fixed
            if self._planning_side_handle == "right":
                size = (world.x - fixed.x) * along.x + (world.y - fixed.y) * along.y
                direction = along
            elif self._planning_side_handle == "left":
                size = (fixed.x - world.x) * along.x + (fixed.y - world.y) * along.y
                direction = Point(-along.x, -along.y)
            elif self._planning_side_handle == "bottom":
                size = (world.x - fixed.x) * across.x + (world.y - fixed.y) * across.y
                direction = across
            else:
                size = (fixed.x - world.x) * across.x + (fixed.y - world.y) * across.y
                direction = Point(-across.x, -across.y)
            if size >= 0.1:
                item.center = Point(fixed.x + direction.x * size / 2,
                                    fixed.y + direction.y * size / 2)
                if self._planning_side_handle in {"left", "right"}:
                    item.length = size
                else:
                    item.width = size
                self.selection_changed.emit(item)
                self.update()
        elif (self._planning_resize_endpoint is not None
              and self.selected_planning
              and self._planning_resize_fixed is not None):
            world = self.screen_to_world(event.position())
            snap_point = self._planning_snap_point(world)
            self.planning_snap_preview = snap_point
            moving = snap_point or world
            if self._planning_resize_endpoint == 0:
                first, second = moving, self._planning_resize_fixed
            else:
                first, second = self._planning_resize_fixed, moving
            self._set_planning_endpoints(self.selected_planning, first, second)
            self.selection_changed.emit(self.selected_planning)
            self.update()
        elif self._dragging_planning and self.selected_planning:
            if not self.selected_planning.locked:
                pointer = self.screen_to_world(event.position())
                offset = self._planning_drag_offset or Point(0, 0)
                self.selected_planning.center = Point(
                    pointer.x + offset.x, pointer.y + offset.y,
                )
                self._snap_planning_to_straight(self.selected_planning)
                self.selection_changed.emit(self.selected_planning)
                self.update()
        elif self.planning_placement and self.planning_draft_start is not None:
            hall = QRectF(
                self.pan.x(), self.pan.y(),
                self.project.hall_length * self.scale,
                self.project.hall_width * self.scale,
            )
            if hall.contains(event.position()):
                world = self.screen_to_world(event.position())
                snap_point = self._planning_snap_point(world)
                self.planning_snap_preview = snap_point
                self.planning_draft_preview = self._constrain_planning_draft(
                    snap_point or world
                )
            else:
                self.planning_snap_preview = None
            self.update()
        elif self.measurement.active:
            if self.measurement.end is None:
                hall = QRectF(
                    self.pan.x(), self.pan.y(),
                    self.project.hall_length * self.scale,
                    self.project.hall_width * self.scale,
                )
                if hall.contains(event.position()):
                    point = self._measurement_point(event.position())
                    if self.measurement.start is not None:
                        self.measurement.preview = point
                else:
                    self.measurement.preview = None
                    self.measurement.snap_point = None
                self.update()
        elif self._guide_drag_axis:
            world = self.screen_to_world(event.position())
            if self._guide_drag_axis == "x":
                self._guide_drag_value = min(self.project.hall_length, max(0.0, self._snap_guide(world.x)))
            else:
                self._guide_drag_value = min(self.project.hall_width, max(0.0, self._snap_guide(world.y)))
            self.status_message.emit(self._tr(
                "Guide: {value} m", value=f"{self._guide_drag_value:g}"
            ))
            self.update()
        elif self._selecting_rect:
            self._rubber_band.setGeometry(QRect(
                self._rubber_origin, event.position().toPoint()).normalized())
        elif self._junction_drag_connector:
            if not self._junction_drag_started and delta.manhattanLength() > 0:
                self._junction_drag_started = True
            if self._junction_drag_started:
                self._move_boundary_junction_to(
                    self._junction_drag_connector,
                    self.screen_to_world(event.position()),
                )
                self.selection_changed.emit(self.selected)
                self.update()
        elif self._magnet_drag_connector:
            if not self._magnet_drag_started and delta.manhattanLength() > 0:
                self._magnet_drag_started = True
            if self._magnet_drag_started:
                self._move_magnet_point_to(self._magnet_drag_connector,
                                           event.position())
                self.selection_changed.emit(self.selected)
                self.update()
        elif self._resize_connector:
            world = self.screen_to_world(event.position())
            if not self._resize_started and delta.manhattanLength() > 0:
                self._resize_started = True
            if self._resize_started:
                self._resize_free_connector_to(self._resize_connector, world)
                element = self.project.element_by_id(self._resize_connector.element_id)
                direct_target = self._free_connector_at_excluding(
                    event.position(), self._resize_connector,
                    self._current_snap_distance(),
                )
                candidate = self._find_snap(element) if element else None
                if direct_target:
                    self.snap_preview = (self._resize_connector, direct_target)
                else:
                    self.snap_preview = ((candidate[1], candidate[2])
                                         if candidate and candidate[1] == self._resize_connector else None)
                self.selection_changed.emit(element)
                self.update()
        elif self._dragging_element and self.selected:
            dx, dy = delta.x() / self.scale, -delta.y() / self.scale
            if not self._drag_started and (abs(dx) > 1e-12 or abs(dy) > 1e-12):
                for connection in list(self.project.connections):
                    first_selected = connection.first.element_id in self.selected_ids
                    second_selected = connection.second.element_id in self.selected_ids
                    if first_selected != second_selected:
                        selected_connector = connection.first if first_selected else connection.second
                        peer_connector = connection.second if first_selected else connection.first
                        selected_element = self.project.element_by_id(selected_connector.element_id)
                        keep_as_joint = (
                            self.project.editor_mode == "indoor"
                            and selected_connector.endpoint.startswith("magnet:")
                            and selected_element is not None
                            and selected_element.element_type == "boundary"
                            and selected_element.kind == "straight"
                        )
                        if keep_as_joint:
                            peer_element = self.project.element_by_id(peer_connector.element_id)
                            other_endpoint = ("end" if peer_connector.endpoint == "start"
                                              else "start")
                            other_connector = ConnectorRef(peer_connector.element_id,
                                                           other_endpoint)
                            other_connection = self.project.connection_for(other_connector)
                            if (peer_element is not None
                                    and peer_element.element_type == "boundary"
                                    and peer_element.kind == "straight"
                                    and peer_connector.endpoint in {"start", "end"}
                                    and other_connection is not None):
                                self._drag_joint_bridges[peer_connector.element_id] = (
                                    peer_connector,
                                    other_connector,
                                    peer_element.pose_at(other_endpoint).point,
                                )
                            else:
                                self._drag_joint_followers.add(peer_connector.element_id)
                            continue
                        self._drag_ignored_pairs.add(frozenset((connection.first.element_id, connection.second.element_id)))
                        self.project.connections.remove(connection)
                self._remember_initial_overlaps()
                self.active_connector = None
                self._drag_started = True
            moved_dx, moved_dy = self._move_selection_safely(dx, dy)
            self._forget_resolved_overlaps()
            dual_candidate = (self._find_dual_boundary_snap(self.selected)
                              if len(self.selected_ids) == 1
                              and not self._drag_joint_followers
                              and not self._drag_joint_bridges else None)
            candidate = (self._find_snap(self.selected)
                         if len(self.selected_ids) == 1 else
                         None if self._drag_joint_followers or self._drag_joint_bridges
                         else self._find_group_snap())
            if dual_candidate:
                self.snap_preview = (
                    ConnectorRef(self.selected.id, "start"), dual_candidate[1],
                    ConnectorRef(self.selected.id, "end"), dual_candidate[2],
                )
            else:
                self.snap_preview = (candidate[1], candidate[2]) if candidate else None
            self.update()
        else:
            w = self.screen_to_world(event.position())
            self.status_message.emit(f"x {w.x:.2f} m · y {w.y:.2f} m")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._panning = False
        if self._planning_side_handle and self.selected_planning:
            before = self._planning_side_before
            self._planning_side_handle = None
            self._planning_side_fixed = None
            self._planning_side_before = None
            if before is not None and self.project != before:
                if self.selected_planning.fits_hall(
                    self.project.hall_length, self.project.hall_width
                ):
                    self._commit_change(
                        self._tr("Resize drivers' stand"), before,
                        (f"planning:{self.selected_planning.id}", ()), None,
                    )
                else:
                    self._restore_without_signal(
                        before, (f"planning:{self.selected_planning.id}", ()), None
                    )
                    self.selection_changed.emit(self.selected_planning)
                    self.status_message.emit(self._tr(
                        "The object would extend beyond the track area."
                    ))
                    self.update()
            return
        if self._planning_resize_endpoint is not None and self.selected_planning:
            before = self._planning_resize_before
            self._planning_resize_endpoint = None
            self._planning_resize_fixed = None
            self._planning_resize_before = None
            self.planning_snap_preview = None
            if before is not None and self.project != before:
                if self.selected_planning.fits_hall(
                    self.project.hall_length, self.project.hall_width
                ):
                    self._commit_change(
                        self._tr("Resize marker"), before,
                        (f"planning:{self.selected_planning.id}", ()), None,
                    )
                else:
                    self._restore_without_signal(
                        before, (f"planning:{self.selected_planning.id}", ()), None
                    )
                    self.selection_changed.emit(self.selected_planning)
                    self.status_message.emit(self._tr(
                        "The object would extend beyond the track area."
                    ))
                    self.update()
            return
        if self._dragging_planning and self.selected_planning:
            before = self._planning_drag_before
            self._dragging_planning = False
            self._planning_drag_before = None
            self._planning_drag_offset = None
            self.planning_snap_preview = None
            if before is not None and self.project != before:
                if self.selected_planning.fits_hall(
                    self.project.hall_length, self.project.hall_width
                ):
                    self._commit_change(
                        self._tr("Move marker"), before,
                        (f"planning:{self.selected_planning.id}", ()), None,
                    )
                else:
                    self._restore_without_signal(
                        before, (f"planning:{self.selected_planning.id}", ()), None
                    )
                    self.selection_changed.emit(self.selected_planning)
                    self.status_message.emit(self._tr("The object would extend beyond the track area."))
                    self.update()
            return
        if self._guide_drag_axis:
            hall = QRectF(self.pan.x(), self.pan.y(), self.project.hall_length * self.scale,
                          self.project.hall_width * self.scale)
            inside = hall.contains(event.position())
            axis = self._guide_drag_axis
            values = self.project.guides_x if axis == "x" else self.project.guides_y
            existing = self._guide_drag_existing
            before = self._guide_drag_before
            if existing:
                values.pop(existing[1])
            if inside and self._guide_drag_value is not None:
                value = self._guide_drag_value
                if not any(abs(item - value) < 1e-9 for item in values):
                    values.append(value); values.sort()
            changed = before is not None and self.project != before
            text = self._tr("Move guide") if existing and inside else self._tr("Delete guide") if existing else self._tr("Add guide")
            self._guide_drag_axis = None
            self._guide_drag_value = None
            self._guide_drag_existing = None
            self._guide_drag_before = None
            self.unsetCursor()
            if changed:
                selection = self._selection_state()
                self._commit_change(text, before, selection, self.active_connector)
            else:
                self.update()
            return
        if self._junction_drag_connector:
            if (self._junction_drag_started
                    and self._junction_drag_before is not None
                    and self.project != self._junction_drag_before):
                self._commit_change(
                    self._tr("Move boundary joint"),
                    self._junction_drag_before,
                    self._junction_drag_before_selection,
                    self._junction_drag_before_connector,
                )
            self._junction_drag_connector = None
            self._junction_drag_started = False
            self._junction_drag_before = None
            self._junction_drag_before_selection = None
            self._junction_drag_before_connector = None
            self.update()
            return
        if self._magnet_drag_connector:
            if self._magnet_drag_started:
                if all(self.project.element_fits_hall(item)
                       for item in self.project.elements):
                    self._commit_change(
                        self._tr("Move magnet point"), self._magnet_drag_before,
                        self._magnet_drag_before_selection,
                        self._magnet_drag_before_connector,
                    )
                else:
                    self._restore_without_signal(
                        self._magnet_drag_before,
                        self._magnet_drag_before_selection,
                        self._magnet_drag_before_connector,
                    )
                    self.status_message.emit(self._tr(
                        "The element would extend beyond the track area."
                    ))
            self._magnet_drag_connector = None
            self._magnet_drag_started = False
            self._magnet_drag_before = None
            self._magnet_drag_before_selection = None
            self._magnet_drag_before_connector = None
            self.update()
            return
        if self._resize_connector:
            if self._resize_started:
                self._finish_connector_resize(event.position())
            self._resize_connector = None
            self._resize_started = False
            self._resize_before = None
            self._resize_before_selection = None
            self._resize_before_connector = None
            self.snap_preview = None
            self.unsetCursor()
            self.update()
            return
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
            changed_ids = (self.selected_ids | self._drag_joint_followers
                           | set(self._drag_joint_bridges))
            if not all(self.project.element_fits_hall(element)
                       for element in self.project.elements
                       if element.id in changed_ids):
                self._restore_without_signal(self._drag_before, self._drag_before_selection,
                                             self._drag_before_connector)
                self.selection_changed.emit(self.selected); self.update()
                self.status_message.emit(self._tr("The element would extend beyond the track area."))
            else:
                if len(self.selected_ids) == 1:
                    if self._drag_joint_followers or self._drag_joint_bridges:
                        self._snap_jointed_boundary(self.selected)
                    else:
                        self._snap_element(self.selected)
                else:
                    self._snap_group()
                self._commit_change(self._tr("Move element"), self._drag_before,
                                    self._drag_before_selection, self._drag_before_connector)
        self.snap_preview = None
        self._dragging_element = False
        self._drag_started = False
        self._drag_before = None
        self._drag_ignored_pairs.clear()
        self._drag_joint_followers.clear()
        self._drag_joint_bridges.clear()
        self.unsetCursor()
        if self.placement:
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif self.measurement.active:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space:
            self._space_pressed = True
            if not self._panning:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            if self.measurement.active:
                self.clear_measurement()
            elif self.planning_placement:
                self.cancel_planning_placement()
            elif self.placement:
                self.cancel_placement()
            else:
                self.clear_selection()
            event.accept()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        elif (event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right)
              and event.modifiers() == Qt.KeyboardModifier.NoModifier
              and (self.selected is not None or self.selected_planning is not None)
              and len(self.selected_ids) <= 1):
            # Native key auto-repeat deliberately drives repeated 5° steps
            # until the user releases the arrow key.
            self.rotate_selected(5 if event.key() == Qt.Key.Key_Left else -5)
            event.accept()
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
                elif self.measurement.active:
                    self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        # Verhindert einen hängenbleibenden Pan-Modus, wenn Alt+Tab oder ein
        # anderes Fenster den KeyRelease-/MouseRelease-Event übernimmt.
        if (self._dragging_planning and self.selected_planning
                and self._planning_drag_before is not None):
            before = self._planning_drag_before
            if self.selected_planning.fits_hall(
                self.project.hall_length, self.project.hall_width
            ):
                self._commit_change(
                    self._tr("Move marker"), before,
                    (f"planning:{self.selected_planning.id}", ()), None,
                )
            else:
                self._restore_without_signal(
                    before, (f"planning:{self.selected_planning.id}", ()), None
                )
            self._dragging_planning = False
            self._planning_drag_before = None
        if self._dragging_element and self.selected and self._drag_started and self._drag_before is not None:
            changed_ids = (self.selected_ids | self._drag_joint_followers
                           | set(self._drag_joint_bridges))
            if all(self.project.element_fits_hall(element)
                   for element in self.project.elements
                   if element.id in changed_ids):
                self._commit_change(self._tr("Move element"), self._drag_before,
                                    self._drag_before_selection, self._drag_before_connector)
            else:
                self._restore_without_signal(self._drag_before, self._drag_before_selection,
                                             self._drag_before_connector)
                self.selection_changed.emit(self.selected); self.update()
                self.status_message.emit(self._tr("The element would extend beyond the track area."))
        if self._resize_started and self._resize_before is not None:
            self._restore_without_signal(self._resize_before, self._resize_before_selection,
                                         self._resize_before_connector)
            self.selection_changed.emit(self.selected); self.update()
        if self._junction_drag_started and self._junction_drag_before is not None:
            self._restore_without_signal(
                self._junction_drag_before,
                self._junction_drag_before_selection,
                self._junction_drag_before_connector,
            )
            self.selection_changed.emit(self.selected); self.update()
        if self._magnet_drag_started and self._magnet_drag_before is not None:
            self._restore_without_signal(
                self._magnet_drag_before,
                self._magnet_drag_before_selection,
                self._magnet_drag_before_connector,
            )
            self.selection_changed.emit(self.selected); self.update()
        self._space_pressed = False
        self._panning = False
        self._selecting_rect = False
        self._rubber_band.hide()
        self._guide_drag_axis = None
        self._guide_drag_value = None
        self._guide_drag_existing = None
        self._guide_drag_before = None
        self._dragging_element = False
        self._drag_started = False
        self._drag_before = None
        self._resize_connector = None
        self._resize_started = False
        self._resize_before = None
        self._resize_before_selection = None
        self._resize_before_connector = None
        self._magnet_drag_connector = None
        self._magnet_drag_started = False
        self._magnet_drag_before = None
        self._magnet_drag_before_selection = None
        self._magnet_drag_before_connector = None
        self._junction_drag_connector = None
        self._junction_drag_started = False
        self._junction_drag_before = None
        self._junction_drag_before_selection = None
        self._junction_drag_before_connector = None
        self.snap_preview = None
        self._drag_ignored_pairs.clear()
        self._drag_joint_followers.clear()
        self._drag_joint_bridges.clear()
        self.unsetCursor()
        if self.placement:
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif self.planning_placement:
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif self.measurement.active:
            self.setCursor(Qt.CursorShape.CrossCursor)
        super().focusOutEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._view_fitted:
            self.fit_to_view()
