"""Temporary measuring-tool state and reusable world-coordinate snap geometry."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, radians, sin

from .model import Point, TrackElement, TrackProject


@dataclass(frozen=True)
class GeometrySnap:
    point: Point
    distance: float
    source: str


@dataclass
class MeasurementState:
    active: bool = False
    start: Point | None = None
    end: Point | None = None
    preview: Point | None = None
    snap_point: Point | None = None

    @property
    def distance(self) -> float | None:
        target = self.end or self.preview
        if self.start is None or target is None:
            return None
        return hypot(target.x - self.start.x, target.y - self.start.y)

    def clear(self) -> None:
        self.start = self.end = self.preview = self.snap_point = None


def _nearest_on_segment(point: Point, start: Point, end: Point) -> Point:
    dx, dy = end.x - start.x, end.y - start.y
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-18:
        return start
    fraction = max(0.0, min(1.0, ((point.x - start.x) * dx +
                                  (point.y - start.y) * dy) / length_sq))
    return Point(start.x + fraction * dx, start.y + fraction * dy)


def _straight_contour_candidates(element: TrackElement, point: Point) -> list[Point]:
    heading = radians(element.heading_deg)
    tangent = Point(cos(heading), sin(heading))
    normal = Point(-tangent.y, tangent.x)
    end = element.end_pose.point
    half = element.width / 2
    start_left = Point(element.start.x + normal.x * half,
                       element.start.y + normal.y * half)
    start_right = Point(element.start.x - normal.x * half,
                        element.start.y - normal.y * half)
    end_left = Point(end.x + normal.x * half, end.y + normal.y * half)
    end_right = Point(end.x - normal.x * half, end.y - normal.y * half)
    return [
        _nearest_on_segment(point, start_left, end_left),
        _nearest_on_segment(point, start_right, end_right),
        _nearest_on_segment(point, start_left, start_right),
        _nearest_on_segment(point, end_left, end_right),
    ]


def _arc_point(center: Point, radius: float, angle: float) -> Point:
    return Point(center.x + radius * cos(angle), center.y + radius * sin(angle))


def _curve_contour_candidates(element: TrackElement, point: Point) -> list[Point]:
    turn = 1 if element.kind == "left" else -1
    heading = radians(element.heading_deg)
    center = Point(
        element.start.x - turn * element.radius * sin(heading),
        element.start.y + turn * element.radius * cos(heading),
    )
    start_angle = heading - turn * pi / 2
    sweep = radians(element.angle_deg)
    query_angle = atan2(point.y - center.y, point.x - center.x)
    progress = ((query_angle - start_angle) % (2 * pi) if turn > 0
                else (start_angle - query_angle) % (2 * pi))
    progress = max(0.0, min(sweep, progress))
    nearest_angle = start_angle + turn * progress
    inner = max(0.0, element.radius - element.width / 2)
    outer = element.radius + element.width / 2
    start_inner = _arc_point(center, inner, start_angle)
    start_outer = _arc_point(center, outer, start_angle)
    end_angle = start_angle + turn * sweep
    end_inner = _arc_point(center, inner, end_angle)
    end_outer = _arc_point(center, outer, end_angle)
    return [
        _arc_point(center, inner, nearest_angle),
        _arc_point(center, outer, nearest_angle),
        _nearest_on_segment(point, start_inner, start_outer),
        _nearest_on_segment(point, end_inner, end_outer),
    ]


def nearest_geometry_snap(
    project: TrackProject,
    point: Point,
    tolerance_metres: float,
) -> GeometrySnap | None:
    """Return the closest visible connector or filled-element contour point."""
    candidates: list[tuple[Point, str]] = []
    for element in project.elements:
        for name in element.connector_names:
            candidates.append((element.pose_at(name).point, "connector"))
        contour = (_straight_contour_candidates(element, point)
                   if element.kind == "straight"
                   else _curve_contour_candidates(element, point))
        candidates.extend((candidate, "contour") for candidate in contour)
    if not candidates:
        return None
    best_point, source = min(
        candidates,
        key=lambda item: hypot(item[0].x - point.x, item[0].y - point.y),
    )
    distance = hypot(best_point.x - point.x, best_point.y - point.y)
    if distance > tolerance_metres:
        return None
    return GeometrySnap(best_point, distance, source)
