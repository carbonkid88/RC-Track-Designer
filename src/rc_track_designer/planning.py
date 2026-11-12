"""Geometry, hit testing and vector rendering for persistent planning markers."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil, cos, radians, sin

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF

from .model import PlanningObject, Point


PointMapper = Callable[[Point], QPointF]


def _world_point(item: PlanningObject, along: float, across: float) -> Point:
    angle = radians(item.heading_deg)
    return Point(
        item.center.x + along * cos(angle) - across * sin(angle),
        item.center.y + along * sin(angle) + across * cos(angle),
    )


def planning_polygon(item: PlanningObject, map_point: PointMapper) -> QPolygonF:
    return QPolygonF([map_point(point) for point in item.corners()])


def planning_hit_test(
    item: PlanningObject,
    screen_point: QPointF,
    map_point: PointMapper,
    tolerance_px: float = 5.0,
) -> bool:
    path = QPainterPath()
    path.addPolygon(planning_polygon(item, map_point))
    if path.contains(screen_point):
        return True
    stroker = QPainterPathStroker()
    stroker.setWidth(tolerance_px * 2)
    return stroker.createStroke(path).contains(screen_point)


def draw_planning_object(
    painter: QPainter,
    item: PlanningObject,
    map_point: PointMapper,
    units_per_metre: float,
    *,
    selected: bool = False,
    grayscale: bool = False,
) -> None:
    """Draw a scale-accurate marker for screen, print or PDF."""
    painter.save()
    polygon = planning_polygon(item, map_point)
    if item.kind == "timing_loop":
        painter.setPen(QPen(QColor("#202020" if grayscale else "#145c2a"),
                            max(0.7, units_per_metre * 0.012)))
        painter.setBrush(QColor("#777777" if grayscale else "#24a148"))
        painter.drawPolygon(polygon)
    else:
        cell = item.width / 2
        across_cells = max(1, int(ceil(item.length / cell)))
        painter.setPen(Qt.PenStyle.NoPen)
        for row in range(2):
            along0 = -item.width / 2 + row * cell
            along1 = min(item.width / 2, along0 + cell)
            for column in range(across_cells):
                across0 = -item.length / 2 + column * cell
                across1 = min(item.length / 2, across0 + cell)
                square = QPolygonF([
                    map_point(_world_point(item, along0, across0)),
                    map_point(_world_point(item, along1, across0)),
                    map_point(_world_point(item, along1, across1)),
                    map_point(_world_point(item, along0, across1)),
                ])
                painter.setBrush(QColor("#111111" if (row + column) % 2 == 0
                                        else "#ffffff"))
                painter.drawPolygon(square)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#111111"), max(0.6, units_per_metre * 0.008)))
        painter.drawPolygon(polygon)
    if selected:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#ffb020"), 3, Qt.PenStyle.SolidLine))
        painter.drawPolygon(polygon)
    painter.restore()
