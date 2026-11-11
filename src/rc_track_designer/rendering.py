"""Shared vector geometry used by the interactive canvas and print output."""

from __future__ import annotations

from collections.abc import Callable
from math import cos, radians, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QPolygonF

from .model import Point, TrackConnection, TrackElement, TrackProject


PointMapper = Callable[[Point], QPointF]


def element_centerline_path(
    element: TrackElement,
    map_point: PointMapper,
    units_per_metre: float,
) -> QPainterPath:
    """Build an exact Qt vector path for an element's centreline."""
    path = QPainterPath(map_point(element.start))
    if element.kind == "straight":
        path.lineTo(map_point(element.end_pose.point))
        return path

    turn = 1 if element.kind == "left" else -1
    heading = radians(element.heading_deg)
    center = Point(
        element.start.x - turn * element.radius * sin(heading),
        element.start.y + turn * element.radius * cos(heading),
    )
    center_device = map_point(center)
    radius = element.radius * units_per_metre
    circle = QRectF(
        center_device.x() - radius,
        center_device.y() - radius,
        2 * radius,
        2 * radius,
    )
    # arcMoveTo prevents Qt from inserting a microscopic line before arcTo.
    # Such a line creates a visible wedge once the path is stroked widely.
    path = QPainterPath()
    path.arcMoveTo(circle, element.heading_deg - turn * 90)
    path.arcTo(
        circle,
        element.heading_deg - turn * 90,
        element.signed_angle_deg,
    )
    return path


def element_filled_shape(
    element: TrackElement,
    map_point: PointMapper,
    units_per_metre: float,
    *,
    width_adjustment: float = 0.0,
) -> QPainterPath:
    """Return the filled scale-accurate road or barrier contour."""
    stroker = QPainterPathStroker()
    stroker.setWidth(max(0.1, element.width * units_per_metre - width_adjustment))
    stroker.setCapStyle(Qt.PenCapStyle.FlatCap)
    stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return stroker.createStroke(
        element_centerline_path(element, map_point, units_per_metre)
    )


def connection_bridge_polygon(
    project: TrackProject,
    connection: TrackConnection,
    map_point: PointMapper,
    units_per_metre: float,
    *,
    half_depth: float,
    half_width_inset: float = 0.0,
) -> QPolygonF:
    """Build the shallow bridge that hides antialiasing gaps at connections."""
    first = project.element_by_id(connection.first.element_id)
    second = project.element_by_id(connection.second.element_id)
    if first is None or second is None:
        return QPolygonF()
    pose = project.connector_pose(connection.first)
    point = map_point(pose.point)
    half_width = max(
        0.0,
        min(first.width, second.width) * units_per_metre / 2 - half_width_inset,
    )
    angle = radians(pose.heading_deg)
    tangent = QPointF(cos(angle), -sin(angle))
    normal = QPointF(sin(angle), cos(angle))
    return QPolygonF([
        point - tangent * half_depth - normal * half_width,
        point + tangent * half_depth - normal * half_width,
        point + tangent * half_depth + normal * half_width,
        point - tangent * half_depth + normal * half_width,
    ])
