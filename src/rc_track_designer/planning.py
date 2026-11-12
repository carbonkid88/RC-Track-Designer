"""Geometry, hit testing and vector rendering for persistent planning markers."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil, cos, radians, sin

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF,
)

from .model import PlanningObject, Point


PointMapper = Callable[[Point], QPointF]


def starting_grid_font_size(units_per_metre: float) -> int:
    """Keep grid numbers readable even when the metric U is zoomed out."""
    return max(14, round(units_per_metre * 0.18))


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
    number: int | None = None,
) -> None:
    """Draw a scale-accurate marker for screen, print or PDF."""
    painter.save()
    polygon = planning_polygon(item, map_point)
    if item.kind == "starting_grid":
        line_width = max(1.5, units_per_metre * 0.025)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        left_top = map_point(_world_point(item, -0.1, -0.25))
        left_bottom = map_point(_world_point(item, -0.1, 0.25))
        right_top = map_point(_world_point(item, 0.1, -0.25))
        right_bottom = map_point(_world_point(item, 0.1, 0.25))
        segments = ((left_top, left_bottom), (left_top, right_top),
                    (left_bottom, right_bottom))
        # A slim dark underlay keeps the prescribed white U visible on the
        # light Classic canvas and on white paper without changing its colour.
        painter.setPen(QPen(QColor("#303030"), line_width + 2,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap,
                            Qt.PenJoinStyle.MiterJoin))
        for start, end in segments:
            painter.drawLine(start, end)
        painter.setPen(QPen(QColor("#ffffff"), line_width,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap,
                            Qt.PenJoinStyle.MiterJoin))
        for start, end in segments:
            painter.drawLine(start, end)
        if number is not None:
            center = map_point(item.center)
            painter.save()
            painter.translate(center)
            painter.rotate(-(item.heading_deg + 90))
            font = QFont(painter.font())
            font.setBold(True)
            font.setPixelSize(starting_grid_font_size(units_per_metre))
            painter.setFont(font)
            text = str(number)
            baseline = QPointF(-painter.fontMetrics().horizontalAdvance(text) / 2,
                               painter.fontMetrics().ascent() / 2)
            text_path = QPainterPath()
            text_path.addText(baseline, font, text)
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(QPen(QColor("#303030"), 1))
            painter.drawPath(text_path)
            painter.restore()
    elif item.kind == "timing_loop":
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
