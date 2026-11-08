"""Qt-Zeichenfläche für Darstellung und direkte Bearbeitung."""

from __future__ import annotations

from copy import deepcopy
from math import atan2, cos, degrees, hypot, radians, sin
from uuid import uuid4

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QFocusEvent, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF, QUndoStack, QWheelEvent
from PySide6.QtWidgets import QMenu, QRubberBand, QWidget

from .commands import ProjectStateCommand
from .closure import ClosureProposal, propose_closure
from .model import ConnectorRef, Point, Pose, TrackConnection, TrackElement, TrackProject


class TrackCanvas(QWidget):
    project_changed = Signal()
    selection_changed = Signal(object)
    status_message = Signal(str)
    closure_connectors_changed = Signal(int)
    close_track_requested = Signal()

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
        self._resize_connector: ConnectorRef | None = None
        self._resize_started = False
        self._resize_before = None
        self._resize_before_selection = None
        self._resize_before_connector = None
        self._drag_ignored_pairs: set[frozenset[str]] = set()
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
        self.connector_hit_distance_px = 10.0
        # A modest angular tolerance makes docking helpful without undoing a
        # deliberate manual rotation from far outside the target tangent.
        self.tangent_tolerance_deg = 30.0
        self.snap_preview: tuple[ConnectorRef, ConnectorRef] | None = None
        self._clipboard_elements: list[TrackElement] = []
        self._clipboard_connections: list[TrackConnection] = []
        self._paste_generation = 0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(640, 400)

    def set_project(self, project: TrackProject) -> None:
        self.project = project
        self.selected = None
        self.selected_ids.clear()
        self.active_connector = None
        self.closure_connectors.clear()
        self.placement = None
        self._resize_connector = None
        self._resize_started = False
        self._resize_before = None
        self.undo_stack.clear()
        self.fit_to_view()
        self.selection_changed.emit(None)
        self.closure_connectors_changed.emit(0)
        self.update()

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
        self.status_message.emit(self._tr("Click inside the track area to place {element}; Esc cancels.", element=label))
        self.update()

    def cancel_placement(self) -> None:
        self.placement = None
        self.unsetCursor()
        self.status_message.emit(self._tr("Selection mode"))
        self.update()

    def clear_selection(self) -> None:
        self.selected = None
        self.selected_ids.clear()
        self.active_connector = None
        self.snap_preview = None
        self.closure_connectors.clear()
        self.closure_connectors_changed.emit(0)
        self.selection_changed.emit(None)
        self.status_message.emit(self._tr("Selection mode"))
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
        if self.selected:
            target_heading = (self.selected.heading_deg + degrees) % 360
            if not self.manual_heading_allowed(self.selected, target_heading):
                self.status_message.emit(self._tr(
                    "Curves can be rotated at most 90° from their placement direction."
                ))
                return
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
        return bool(self.selected and self.manual_heading_allowed(
            self.selected, self.selected.heading_deg + degrees
        ))

    @staticmethod
    def manual_heading_allowed(element: TrackElement, heading_deg: float) -> bool:
        if element.kind == "straight":
            return True
        reference = element.rotation_reference_deg
        if reference is None:
            reference = element.heading_deg
        delta = (heading_deg - reference + 180) % 360 - 180
        return -90.0 - 1e-9 <= delta <= 90.0 + 1e-9

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
            if not self.manual_heading_allowed(self.selected, target):
                self._restore_without_signal(before, before_selection, before_connector)
                self.selection_changed.emit(self.selected); self.update()
                self.status_message.emit(self._tr(
                    "Curves can be rotated at most 90° from their placement direction."
                ))
                return
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

    def _free_connector_at_excluding(self, pos: QPointF,
                                     excluded: ConnectorRef,
                                     maximum_distance: float | None = None) -> ConnectorRef | None:
        best = None
        best_distance = (self.connector_hit_distance_px if maximum_distance is None
                         else maximum_distance)
        for element in self.project.elements:
            if element.id == excluded.element_id:
                continue
            endpoint = "end" if excluded.endpoint == "start" else "start"
            connector = ConnectorRef(element.id, endpoint)
            if not self.project.is_free(connector):
                continue
            screen = self.world_to_screen(element.pose_at(endpoint).point)
            distance = hypot(screen.x() - pos.x(), screen.y() - pos.y())
            if distance <= best_distance:
                best, best_distance = connector, distance
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
            self.status_message.emit(self._tr("The element would extend beyond the track area."))
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
                if distance <= self.snap_distance_px:
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
                opposite = "end" if own_endpoint == "start" else "start"
                for other in self.project.elements:
                    if other.id in selected_ids:
                        continue
                    candidate = ConnectorRef(other.id, opposite)
                    if not self.project.is_free(candidate):
                        continue
                    target = other.pose_at(opposite)
                    target_screen = self.world_to_screen(target.point)
                    distance = hypot(screen.x() - target_screen.x(),
                                     screen.y() - target_screen.y())
                    angle = self._angle_difference(pose.heading_deg,
                                                   target.heading_deg)
                    if distance <= self.snap_distance_px:
                        score = distance + angle * 0.02
                        if best is None or score < best[0]:
                            best = (score, own, candidate, target)
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

    def overlapping_element_ids(self) -> set[str]:
        connected_pairs = {
            frozenset((connection.first.element_id, connection.second.element_id))
            for connection in self.project.connections
        }
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
        elements = [item for item in self.project.elements if item.id in self.selected_ids]
        dx, dy = self.project.clamp_group_translation(elements, dx, dy)
        if abs(dx) <= 1e-12 and abs(dy) <= 1e-12: return 0.0, 0.0
        for item in elements: item.moved(dx, dy)
        return dx, dy

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
        if self.project.connection_for(fixed_connector) is None:
            return False
        fixed_pose = element.pose_at(fixed_endpoint)
        before = deepcopy(element)
        if element.kind == "straight":
            direction = fixed_pose.heading_deg + (180 if fixed_endpoint == "end" else 0)
            angle = radians(direction)
            length = ((point.x - fixed_pose.point.x) * cos(angle)
                      + (point.y - fixed_pose.point.y) * sin(angle))
            if snap_values:
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
                release_position, connector, self.snap_distance_px
            )
            if direct_target:
                candidate = (0.0, connector, direct_target,
                             self.project.connector_pose(direct_target))
        connected = False
        if candidate and candidate[1] == connector:
            _score, own, other, target = candidate
            before_fit = deepcopy(element)
            if self._resize_free_connector_to(connector, target.point, snap_values=False):
                own_pose = element.pose_at(connector.endpoint)
                distance = hypot(own_pose.point.x - target.point.x,
                                 own_pose.point.y - target.point.y)
                angle = self._angle_difference(own_pose.heading_deg, target.heading_deg)
                if distance <= 1e-6 and angle <= 1e-6:
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
            if (event.modifiers() & Qt.KeyboardModifier.ControlModifier
                    and self.project.is_free(connector)):
                self.toggle_closure_connector(connector)
                return
            element = self.project.element_by_id(connector.element_id)
            self.selected = element
            self.selected_ids = {element.id}
            self.active_connector = connector if self.project.is_free(connector) else None
            other_endpoint = "end" if connector.endpoint == "start" else "start"
            if (self.active_connector
                    and self.project.connection_for(ConnectorRef(element.id, other_endpoint))):
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

    def _delete_guide(self, guide: tuple[str, int, float]) -> None:
        axis, index, _value = guide
        before = deepcopy(self.project)
        before_selection = self._selection_state()
        before_connector = self.active_connector
        values = self.project.guides_x if axis == "x" else self.project.guides_y
        values.pop(index)
        self._commit_change(self._tr("Delete guide"), before,
                            before_selection, before_connector)

    def _build_context_menu(self, connector: ConnectorRef | None,
                            guide: tuple[str, int, float] | None) -> QMenu | None:
        connection = self.project.connection_for(connector) if connector else None
        can_close = len(self.closure_connectors) == 2
        if not (connection or guide or can_close):
            return None
        menu = QMenu(self)
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
        return menu

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        connector = self._connector_at(event.pos())
        guide = self._guide_at(QPointF(event.pos()))
        connection = self.project.connection_for(connector) if connector else None
        if guide and not connection and len(self.closure_connectors) != 2:
            self._delete_guide(guide)
            event.accept()
            return
        menu = self._build_context_menu(connector, guide)
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
        elif self._resize_connector:
            world = self.screen_to_world(event.position())
            if not self._resize_started and delta.manhattanLength() > 0:
                self._resize_started = True
            if self._resize_started:
                self._resize_free_connector_to(self._resize_connector, world)
                element = self.project.element_by_id(self._resize_connector.element_id)
                direct_target = self._free_connector_at_excluding(
                    event.position(), self._resize_connector,
                    self.snap_distance_px,
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
                        self._drag_ignored_pairs.add(frozenset((connection.first.element_id, connection.second.element_id)))
                        self.project.connections.remove(connection)
                self._remember_initial_overlaps()
                self.active_connector = None
                self._drag_started = True
            moved_dx, moved_dy = self._move_selection_safely(dx, dy)
            self._forget_resolved_overlaps()
            candidate = (self._find_snap(self.selected)
                         if len(self.selected_ids) == 1 else self._find_group_snap())
            self.snap_preview = (candidate[1], candidate[2]) if candidate else None
            self.update()
        else:
            w = self.screen_to_world(event.position())
            self.status_message.emit(f"x {w.x:.2f} m · y {w.y:.2f} m")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._panning = False
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
            if not self.project.element_fits_hall(self.selected):
                self._restore_without_signal(self._drag_before, self._drag_before_selection,
                                             self._drag_before_connector)
                self.selection_changed.emit(self.selected); self.update()
                self.status_message.emit(self._tr("The element would extend beyond the track area."))
            else:
                if len(self.selected_ids) == 1:
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
            if self.placement:
                self.cancel_placement()
            else:
                self.clear_selection()
            event.accept()
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
                self.status_message.emit(self._tr("The element would extend beyond the track area."))
        if self._resize_started and self._resize_before is not None:
            self._restore_without_signal(self._resize_before, self._resize_before_selection,
                                         self._resize_before_connector)
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
